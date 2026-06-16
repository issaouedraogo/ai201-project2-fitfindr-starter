"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.style_profiles import load_profile, enhance_search_with_profile
import re


# ── helper: retry logic ──────────────────────────────────────────────────────

def _search_with_retry(description: str, size: str | None, max_price: float | None) -> tuple[list, dict]:
    """
    Attempt search with automatic fallback/retry strategy.
    
    Returns: (results, retry_info) where:
    - results: list of matching items (empty if all attempts fail)
    - retry_info: dict with 'attempts', 'final_filters', 'message'
    
    Strategy:
    1. Attempt 1: Search with all filters (description, size, max_price)
    2. Attempt 2: If empty, retry without size
    3. Attempt 3: If still empty, retry without size and +25% price
    4. If all fail: Return empty list with error message
    """
    retry_info = {"attempts": [], "final_filters": None, "message": None}
    
    # Attempt 1: Initial search with all filters
    retry_info["attempts"].append({"filters": f"description='{description}', size={size}, max_price={max_price}"})
    results = search_listings(description, size=size, max_price=max_price)
    if results:
        retry_info["final_filters"] = {"description": description, "size": size, "max_price": max_price}
        retry_info["message"] = None
        return results, retry_info
    
    # Attempt 2: Remove size constraint
    if size:
        retry_info["attempts"].append({"filters": f"description='{description}', size=None, max_price={max_price}"})
        results = search_listings(description, size=None, max_price=max_price)
        if results:
            retry_info["final_filters"] = {"description": description, "size": None, "max_price": max_price}
            retry_info["message"] = f"Relaxed search: removed size filter '{size}' to find results."
            return results, retry_info
    
    # Attempt 3: Remove size AND increase price by 25%
    if max_price:
        increased_price = max_price * 1.25
        retry_info["attempts"].append({"filters": f"description='{description}', size=None, max_price={increased_price}"})
        results = search_listings(description, size=None, max_price=increased_price)
        if results:
            retry_info["final_filters"] = {"description": description, "size": None, "max_price": increased_price}
            price_increase = increased_price - max_price
            retry_info["message"] = f"Relaxed search: removed size filter '{size}' and increased max price from ${max_price:.0f} to ${increased_price:.0f}."
            return results, retry_info
    
    # All attempts failed
    retry_info["message"] = (
        f"No results found after trying: (1) your original filters (size: {size}, max price: ${max_price}), "
        f"(2) without size, (3) without size and 25% higher price. "
        f"Try: (1) broadening your keywords, (2) searching for a different style, (3) increasing your budget significantly."
    )
    return [], retry_info


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "retry_info": None,          # retry attempt details (if search needed retries)
        "profile": None,             # loaded style profile (if user_id provided)
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict, user_id: str | None = None) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    # Step 1b: Load style profile if user_id provided
    profile = None
    if user_id:
        profile = load_profile(user_id)
        session["profile"] = profile

    # Step 2: Parse query for price and size
    q = query or ""
    # max price: look for 'under $30' or 'under 30' or '$30'
    price_match = re.search(r"under\s*\$?(\d+(?:\.\d+)?)", q, flags=re.IGNORECASE)
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", q)
    max_price = float(price_match.group(1)) if price_match else None

    # size: look for 'size M' or 'size: M' or just ' size M'
    size_match = re.search(r"size\s*[:]?\s*([A-Za-z0-9/]+)", q, flags=re.IGNORECASE)
    size = size_match.group(1) if size_match else None

    # description: remove explicit phrases
    desc = q
    if price_match:
        desc = re.sub(price_match.group(0), "", desc, flags=re.IGNORECASE)
    if size_match:
        desc = re.sub(size_match.group(0), "", desc, flags=re.IGNORECASE)
    desc = desc.strip()
    if not desc:
        desc = q

    # Apply style profile defaults (only fills in values the query didn't provide)
    if profile:
        if not size and profile.get("preferred_sizes"):
            size = profile["preferred_sizes"][0]
        if max_price is None and profile.get("budget_range", {}).get("max"):
            max_price = float(profile["budget_range"]["max"])
        desc = enhance_search_with_profile(desc, profile)

    session["parsed"] = {"description": desc, "size": size, "max_price": max_price}

    # Step 3: Call search_listings with retry logic
    try:
        results, retry_info = _search_with_retry(desc, size, max_price)
        session["retry_info"] = retry_info
    except Exception as e:
        session["error"] = "Temporary data error — please try again later."
        session["error_details"] = str(e)
        return session

    session["search_results"] = results
    if not results:
        print("State: EvaluateSearch — no results found")
        session["error"] = retry_info["message"]
        return session

    # Step 4: select top result
    top = results[0]
    session["selected_item"] = top

    # Step 5: suggest outfit
    try:
        outfit_text = suggest_outfit(top, wardrobe)
    except Exception as e:
        session["error"] = "Failed to create outfit suggestion."
        session["error_details"] = str(e)
        return session

    session["outfit_suggestion"] = outfit_text

    # Step 6: create fit card
    try:
        fit_card = create_fit_card(outfit_text, top)
    except Exception as e:
        session["error"] = "Failed to create fit card."
        session["error_details"] = str(e)
        return session

    session["fit_card"] = fit_card
    session["error"] = None
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
