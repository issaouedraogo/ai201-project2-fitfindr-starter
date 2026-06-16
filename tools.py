"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os


from utils.data_loader import load_listings
import re
from typing import List


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # normalize
    desc = (description or "").lower()
    query_tokens = re.findall(r"\w+", desc)

    results: List[dict] = []

    for item in listings:
        # Price filter
        price = item.get("price")
        if max_price is not None and price is not None:
            try:
                if float(price) > float(max_price):
                    continue
            except Exception:
                pass

        # Size matching: accept if requested size token appears in item's size string
        item_size = (item.get("size") or "").lower()
        if size:
            s = size.lower()
            if s not in item_size and s not in re.findall(r"\b\w\b", item_size):
                # not a direct match — skip
                continue

        # Scoring: keyword overlap with title/description and tag overlap
        title = (item.get("title") or "").lower()
        description_text = (item.get("description") or "").lower()
        style_tags = [t.lower() for t in item.get("style_tags") or []]

        keyword_matches = 0
        for tok in query_tokens:
            if tok in title or tok in description_text:
                keyword_matches += 1
            if tok in style_tags:
                keyword_matches += 1

        if keyword_matches == 0:
            # no overlap with user's query
            continue

        # basic score: keyword matches (+ tag matches implicit above)
        score = float(keyword_matches)

        result = item.copy()
        result["score"] = score
        result["snippet"] = (description_text[:140] + "...") if description_text else ""
        results.append(result)

    # sort by score desc, then price asc
    results.sort(key=lambda r: (-r.get("score", 0), r.get("price", 0)))
    return results[:limit]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict, max_items: int = 3) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    items = wardrobe.get("items") if isinstance(wardrobe, dict) else None
    if not items:
        return (
            "I don't see any items in your wardrobe — try adding some pieces or "
            "run the demo with the example wardrobe. In the meantime, general styling: "
            f"Pair the {new_item.get('title','item')} with high-waisted bottoms and chunky shoes for a balanced look."
        )

    # Score wardrobe items by tag overlap and color relevance
    new_tags = set([t.lower() for t in (new_item.get("style_tags") or [])])
    new_colors = set([c.lower() for c in (new_item.get("colors") or [])])

    scored = []
    for w in items:
        w_tags = set([t.lower() for t in (w.get("style_tags") or [])])
        w_colors = set([c.lower() for c in (w.get("colors") or [])])
        tag_score = len(new_tags & w_tags)
        color_score = len(new_colors & w_colors)
        total = tag_score * 2 + color_score
        scored.append((total, tag_score, color_score, w))

    scored.sort(key=lambda x: (-x[0], -x[1], -x[2]))
    chosen = [entry[3] for entry in scored if entry[0] > 0][:max_items]

    if not chosen:
        # fallback: pick up to max_items by category preference
        pref_order = ["bottoms", "shoes", "outerwear", "accessories", "tops"]
        chosen = []
        for cat in pref_order:
            for _, _, _, w in scored:
                if w.get("category") == cat and w not in chosen:
                    chosen.append(w)
                    if len(chosen) >= max_items:
                        break
            if len(chosen) >= max_items:
                break

    # Build styling text
    chosen_names = [c.get("name") for c in chosen]
    if chosen_names:
        items_text = ", ".join(chosen_names)
        styling = (
            f"Pair the {new_item.get('title')} with {items_text}. "
            "Try a slight front tuck or cuffing the hem to balance proportions."
        )
    else:
        styling = (
            f"This {new_item.get('title')} is versatile — try pairing with high-waisted bottoms and chunky shoes for a balanced silhouette."
        )

    return styling


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict, tone: str = "casual", max_length: int = 280) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not new_item:
        return "Error: missing item data for fit card."

    title = new_item.get("title") or "this item"
    price = new_item.get("price")
    platform = new_item.get("platform")

    price_part = f" for ${price:.0f}" if isinstance(price, (int, float)) else ""
    platform_part = f" on {platform}" if platform else ""

    base = f"Thrifted {title}{price_part}{platform_part}. {outfit}"
    if len(base) > max_length:
        base = base[: max_length - 3] + "..."
    return base


# ── Tool 4: price_comparison (Extra Credit) ───────────────────────────────────

def price_comparison(item: dict) -> str:
    """
    Estimate whether an item's price is fair based on comparable listings.

    Args:
        item: A listing dict (the item to evaluate).

    Returns:
        A string assessment of the price fairness, including:
        - Fair/good/great deal/overpriced rating
        - Average price of comparable items
        - Item's price relative to market
        - Number of comparable items found

    Comparables are identified by:
    - Same or similar category
    - Similar condition (exact match if available)
    - Overlapping style tags (at least one match)
    - Similar price range (within 50% of median)

    Returns graceful error message if item data is missing or no comparables found.
    """
    if not item:
        return "Error: missing item data for price comparison."

    listings = load_listings()
    item_price = item.get("price")
    item_category = (item.get("category") or "").lower()
    item_condition = (item.get("condition") or "").lower()
    item_tags = set([t.lower() for t in (item.get("style_tags") or [])])

    if item_price is None:
        return "Error: item price not available for comparison."

    try:
        item_price = float(item_price)
    except (ValueError, TypeError):
        return "Error: invalid price format."

    # Find comparable items
    comparables = []
    for other in listings:
        # Skip the item itself
        if other.get("id") == item.get("id"):
            continue

        other_price = other.get("price")
        other_category = (other.get("category") or "").lower()
        other_condition = (other.get("condition") or "").lower()
        other_tags = set([t.lower() for t in (other.get("style_tags") or [])])

        try:
            other_price = float(other_price)
        except (ValueError, TypeError):
            continue

        # Must be same or similar category
        if item_category and other_category and item_category != other_category:
            continue

        # Should have condition match or both unspecified
        if item_condition and other_condition and item_condition != other_condition:
            continue

        # Must have at least one overlapping tag
        if item_tags and other_tags:
            if not (item_tags & other_tags):  # no intersection
                continue

        comparables.append(other_price)

    # If no comparables, return message
    if not comparables:
        return (
            f"No comparable items found in dataset to assess this {item_category or 'item'}. "
            f"Price: ${item_price:.2f}. Consider market trends or similar thrift platforms."
        )

    # Calculate statistics
    comparables.sort()
    count = len(comparables)
    min_price = comparables[0]
    max_price = comparables[-1]
    avg_price = sum(comparables) / count
    median_price = comparables[count // 2] if count % 2 == 1 else (comparables[count // 2 - 1] + comparables[count // 2]) / 2

    # Determine fairness
    if item_price <= min_price * 0.85:
        rating = "Great deal! 🔥"
        assessment = "This is significantly cheaper than comparable items."
    elif item_price <= avg_price * 0.90:
        rating = "Good price"
        assessment = "Below average for similar items."
    elif item_price <= avg_price * 1.10:
        rating = "Fair price"
        assessment = "Right around the market average."
    elif item_price <= max_price * 1.15:
        rating = "Slightly expensive"
        assessment = "Above typical market price."
    else:
        rating = "Overpriced"
        assessment = "Significantly higher than comparable items."

    # Build comparison summary
    summary = (
        f"{rating} — {assessment}\n"
        f"Your item: ${item_price:.2f}\n"
        f"Comparables (n={count}): ${min_price:.2f}–${max_price:.2f}, avg: ${avg_price:.2f}, median: ${median_price:.2f}"
    )

    return summary


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Tools Demo ===\n")

    # Search
    print("1. Searching for 'vintage graphic tee':\n")
    results = search_listings("vintage graphic tee", limit=2)
    for item in results:
        print(f"  • {item['title']} — ${item['price']} (score: {item['score']})")
    
    if results:
        item = results[0]
        
        # Outfit suggestion
        print(f"\n2. Suggesting outfit for '{item['title']}':\n")
        outfit = suggest_outfit(item, get_example_wardrobe())
        print(f"  {outfit}")
        
        # Fit card
        print(f"\n3. Creating fit card:\n")
        caption = create_fit_card(outfit, item)
        print(f"  {caption}")
        
        # Price comparison
        print(f"\n4. Price comparison:\n")
        comparison = price_comparison(item)
        for line in comparison.split("\n"):
            print(f"  {line}")
