# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**

Search the listings dataset for items matching the user's query and filter parameters, score results by relevance (keyword + `style_tags` overlap + price proximity), and return top-N candidates sorted by score.

**Input parameters:**

- `query` (str): user search text, e.g., "vintage graphic tee" (required).
- `size` (str | None): optional size filter (e.g., "M", "S/M"); match loosely for ranges like "S/M".
- `max_price` (float | None): optional maximum price in USD.
- `category` (str | None): optional category constraint (tops, bottoms, outerwear, shoes, accessories).
- `style_tags` (list[str] | None): optional tags to boost (e.g., ["grunge", "vintage"]).
- `limit` (int): number of results to return (default 5).

**What it returns:**

Returns a list (possibly empty) of listing dicts. Each result includes: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str|null), `platform` (str), plus `snippet` (str) and `score` (float) for ranking.

**What happens if it fails or returns nothing:**

If loading/parsing the dataset fails, surface a concise system error and suggest retrying later. If no matches are found, halt downstream calls and return a helpful message with 3 concrete suggestions: (1) increase `max_price`, (2) relax or remove `size`, (3) broaden keywords. Offer to re-run with adjusted filters; track retry counts to avoid infinite loops.

---

### Tool 2: suggest_outfit

**What it does:**

Given a selected listing (`new_item`) and the user's `wardrobe`, pick 1–4 complementary wardrobe items and produce a concise styling explanation with reasons for each selection.

**Input parameters:**

- `new_item` (dict): listing dict returned by `search_listings` (must include `category`, `style_tags`, `colors`).
- `wardrobe` (dict): object with `items` list following `wardrobe_schema.json` (each item: `id`, `name`, `category`, `colors`, `style_tags`, `notes`).
- `preferences` (dict | optional): e.g., `{"favor": "cozy"}` to bias suggestions.
- `max_items` (int): maximum wardrobe items to include (default 3).

**What it returns:**

Returns an `outfit` dict with: `items` (list[dict] — chosen wardrobe items), `new_item` (dict — passthrough listing), `styling_text` (str — user-facing styling paragraph), `reasons` (list[str] — bullet reasons linking selections to tags/colors).

**What happens if it fails or returns nothing:**

If `wardrobe['items']` is empty, return `{ "items": [], "styling_text": "..." }` explaining how to add items or offering a demo with `get_example_wardrobe()`; do not call `create_fit_card`. If no confident matches exist, return best-effort suggestions ranked by confidence and recommend alternatives.

---

### Tool 3: create_fit_card

**What it does:**

Produce a short, shareable caption (fit card) summarizing the thrifted listing and suggested outfit in a natural, social-media style tone.

**Input parameters:**

- `outfit` (dict): the `outfit` object returned by `suggest_outfit` (must include `items`, `new_item`, `styling_text`).
- `tone` (str | optional): writing tone (e.g., "casual", "playful"); default "casual".
- `max_length` (int | optional): max caption length (default 280).

**What it returns:**

Returns a `fit_card` dict: `caption` (str — short caption suitable for sharing), `summary` (str — one-line summary), `metadata` (dict — e.g., `{ 'new_item_id': 'lst_006', 'wardrobe_item_ids': ['w_001'], 'platform': 'depop' }`).

**What happens if it fails or returns nothing:**

If required fields are missing from `outfit` or `new_item`, attempt a templated fallback caption using available data. If synthesis is impossible, return a clear error and ask whether to proceed with a templated caption or abort.

---

### Additional Tools (if any)

- `load_listings()` / `get_example_wardrobe()` / `get_empty_wardrobe()` — use `utils.data_loader` helpers rather than re-reading files.
- `session_store` — in-memory per-session dict with optional JSON persistence; methods: `get(session_id)`, `set(session_id, state)`, `clear(session_id)`.
- `logger` — structured logging helper used to record errors and key planner decisions.

---

## Extra Credit: Style Profile Memory

**Feature:** Allow the agent to remember a user's style preferences across sessions so they don't have to re-describe their wardrobe or preferences every time.

**How it works:**

1. `run_agent()` accepts an optional `user_id` parameter.
2. If `user_id` is provided, the agent calls `load_profile(user_id)` from `utils/style_profiles.py`.
3. If a profile exists, its data is applied before search:
   - `preferred_styles` are appended to the search description via `enhance_search_with_profile()`.
   - `preferred_sizes[0]` fills in the size filter when the user's query doesn't specify one.
   - `budget_range.max` fills in `max_price` when the query doesn't specify a price.
4. The loaded profile is stored in `session["profile"]` for transparency.
5. If no profile exists for the given `user_id`, the agent proceeds normally without error.

**Profile schema (stored as JSON in `data/profiles/<user_id>.json`):**

```
{
  "user_id": str,
  "preferred_colors":     list[str],   # e.g. ["black", "navy"]
  "preferred_styles":     list[str],   # e.g. ["vintage", "minimalist"]
  "preferred_categories": list[str],   # e.g. ["tops", "outerwear"]
  "preferred_sizes":      list[str],   # e.g. ["M", "S/M"]
  "budget_range":         {"min": float, "max": float},
  "notes":                str,
  "created_at":           ISO-8601 str,
  "updated_at":           ISO-8601 str
}
```

**Utility module:** `utils/style_profiles.py`
- `create_profile(user_id, ...)` — create and persist a profile
- `load_profile(user_id)` — load from disk; returns None if not found
- `update_profile(user_id, **fields)` — update specific fields
- `delete_profile(user_id)` — remove profile file
- `enhance_search_with_profile(query, profile)` — augments query with style preferences

**State changes:**
- `session["profile"]` — the loaded profile dict, or None if not found/not requested

**Error handling:**
- Missing profile → proceed as if no `user_id` was passed (no crash, no error message)
- Corrupt profile file → `load_profile` returns None; agent proceeds normally
- Profile's size/budget only apply as *defaults*; explicit query values always win

---

## Extra Credit: Retry Logic with Fallback

**Feature:** If initial search returns no results, automatically retry with relaxed constraints rather than immediately failing.

**Retry Strategy:**

1. **Attempt 1 (Initial)** — Search with all filters (query, size, max_price)
2. **Attempt 2 (Relax Size)** — If no results: remove size filter, keep query & price
3. **Attempt 3 (Relax Price)** — If still no results: remove size, increase max_price by 25%
4. **Final** — After 3 attempts, return error message explaining what was tried

**What it returns:**

- Success: Search results from any attempt (returns earliest successful attempt)
- Failure: Error message listing retry attempts and suggesting next steps
- Metadata: Includes in session which retry attempt succeeded (or all failed)

**Benefits:**

- Users get results instead of immediate "no results" error
- Graceful degradation of constraints instead of hard failure
- Transparent: user informed what relaxations were applied
- Retries only automatic if initial search fails (not just for loose matches)

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planner is a deterministic state machine with these major states:

1. **ParseInput** — normalize user query into `filters` (query, size, max_price, category, style_tags).
2. **Search** — call `search_listings(filters)`; store results.
3. **EvaluateSearch** — if `results` is empty, go to `SearchFailure` and end or prompt for retry; else select `top_result` (highest `score`) and proceed to `OutfitSuggestion`.
4. **OutfitSuggestion** — call `suggest_outfit(new_item=top_result, wardrobe=current_wardrobe)`; if `outfit.items` is empty, go to `WardrobeFallback` and stop; else proceed to `FitCardCreation`.
5. **FitCardCreation** — call `create_fit_card(outfit)` and produce final response.
6. **Done** — return structured reply: `{ search_results, chosen_listing, outfit, fit_card }`.

**Decision rules:** Top result is highest `score`. If size doesn't match but is reasonable (e.g., "S/M" for requested "M"), reduce score slightly but allow. Track `search_retries`; after 2 automatic retries with relaxation strategies (price +25%, drop size), stop and ask user explicitly. Accept follow-up commands: "show next" (increment index), "broaden price" (adjust and re-run Search), "use example wardrobe" (demo with example).

**Termination:** Successful `fit_card` creation, explicit user cancel, or exhausting retry strategies.

---

## State Management

**How does information from one tool get passed to the next?**

Session state schema (stored in-memory):

```
{
  "session_id": "str",
  "user_query": "str",
  "filters": { "query": "", "size": null, "max_price": null, "category": null },
  "search_results": [ ... ],
  "selected_index": 0,
  "chosen_listing": null,
  "wardrobe": { "items": [...] },
  "outfit": null,
  "fit_card": null,
  "search_retries": 0,
  "last_error": null
}
```

Data flows between tools as follows:

- Planner composes `filters` and calls `search_listings(filters)`; stores `search_results` in state.
- Planner reads `selected_index` to pick `chosen_listing`, then calls `suggest_outfit(chosen_listing, wardrobe)`; stores `outfit` in state.
- Planner calls `create_fit_card(outfit)` and stores `fit_card` in state.
- All tool calls use explicit parameters from state; no tool mutates global state directly.
- Optional JSON persistence for debugging or session restoration.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool            | Failure mode                   | Agent response                                                                                                                      |
| --------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| search_listings | No results match the query     | Return guidance: increase `max_price`, relax `size`, broaden `query`. Offer to re-run with changes. Increment `search_retries`.     |
| search_listings | IO / parse error               | Surface: "Temporary data error — please try again later." Log full error; fail safe with cached results if available.               |
| suggest_outfit  | Wardrobe is empty              | Return `items: []` with `styling_text` offering to add items or demo using `get_example_wardrobe()`; do not call `create_fit_card`. |
| suggest_outfit  | No confident matches           | Return best-effort suggestions ranked by confidence; recommend alternatives (different `max_items`, example wardrobe).              |
| create_fit_card | Missing outfit/new_item fields | Attempt templated caption with available data; if insufficient, return error asking whether to proceed with template or abort.      |

---

## Architecture

```mermaid
flowchart TD
  User[User input]
  Parser[ParseInput]
  Planner[Planner Loop]
  Search[search_listings]
  Eval[EvaluateSearch]
  Suggest[suggest_outfit]
  FitCard[create_fit_card]
  Session[Session Store]
  User --> Parser --> Planner
  Planner --> Search --> Session
  Search --> Eval
  Eval -- no results --> User
  Eval -- has results --> Suggest --> FitCard --> User
  Planner <--> Session
  Search -->|loads data| load_listings[load_listings()]
  Suggest -->|reads wardrobe| load_wardrobe[get_example_wardrobe()]
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- Give AI the `search_listings` spec (inputs, outputs, failure modes) and ask for a Python function using `utils.data_loader.load_listings()`. Verify with 3 sample queries: exact keyword match, tag overlap match, and price-limited no-result case.
- Give AI the `suggest_outfit` spec and ask for an implementation with tag-overlap heuristics returning `outfit` dict. Verify using both `get_example_wardrobe()` and `get_empty_wardrobe()`.
- Give AI the `create_fit_card` spec and ask for caption templates with optional `tone` parameter. Verify by asserting presence of key strings (item title, price, platform) and max length compliance.

**Milestone 4 — Planning loop and state management:**

- Ask AI to implement a `Planner` class using the three tools, storing state in a session dict, and exposing a `run_agent(query, wardrobe)` method that returns the final structured response. Verify by running end-to-end integration tests simulating the example interaction and error paths.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."

**Step 1 — Parse input:**

- Extract `query="vintage graphic tee"`, `size="M"`, `max_price=30.0` from user text.
- Store in session state `filters`.

**Step 2 — Call search_listings:**

- `search_listings(query="vintage graphic tee", size="M", max_price=30.0, limit=5)`
- Returns (example):
  - Result 1: `{ "id": "lst_006", "title": "Faded Band Tee", "price": 22.0, "category": "tops", "style_tags": ["vintage","band tee","grunge"], "score": 0.92 }`
  - Result 2, 3, ... (lower scores)
- Store `search_results` in session state.

**Step 3 — Evaluate and select:**

- Take top result (highest score): `lst_006` "Faded Band Tee".
- Store as `chosen_listing` in session.

**Step 4 — Call suggest_outfit:**

- `suggest_outfit(new_item=chosen_listing, wardrobe=get_example_wardrobe())`
- Matches: `w_001` (baggy jeans \u2014 tag overlap), `w_007` (chunky white sneakers \u2014 color/tag match)
- Returns `outfit`:
  - `items: [w_001, w_007]`
  - `styling_text: "Pair this faded band tee with your baggy straight-leg jeans and chunky white sneakers. Tuck the front slightly and roll the sleeves once for shape."`
  - `reasons: ["tag overlap: vintage/denim", "silhouette balance: boxy tee + baggy jeans"]`
- Store `outfit` in session.

**Step 5 — Call create_fit_card:**

- `create_fit_card(outfit, tone="casual", max_length=280)`
- Returns `fit_card`:
  - `caption: "Thrifted this faded band tee off Depop for $22 — made for my baggy jeans and chunky sneakers. Threw it on with a half-tuck and rolled sleeves. #thrifted #bandtee"`
  - `summary: "Faded band tee — $22, pair with baggy jeans & chunky sneakers"`
- Store `fit_card` in session.

**Final output to user:**

- **Top listing:** \"Faded Band Tee\" — $22 on Depop, excellent condition, vintage band-tee vibes.
- **Suggested outfit:** Pair with your baggy straight-leg jeans and chunky white sneakers. Tuck the front slightly and roll the sleeves once for shape.
- **Fit card caption:** (ready to share) \"Thrifted this faded band tee off Depop for $22...\"
- **Actions:** \"Show next\", \"Broaden price\", \"Use example wardrobe\", \"Save caption\".

**Error path example — If search returns no results:**

- Planner returns: \"No results found. Try: (1) increase your max price to $40, (2) change size to S/M or One Size, (3) search for 'graphic tee' only. Would you like me to try one of these?\"
- Increment `search_retries` and wait for user choice; do NOT call `suggest_outfit` or `create_fit_card`.
