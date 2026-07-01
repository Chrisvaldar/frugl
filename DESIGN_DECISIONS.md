# Design Decisions

Product and engineering choices for **Frugl**. The sections at the top are the ones that actually drive compare results.

---

## How compare picks products (quick map)

| List source | Store search | Pick match per store |
|-------------|--------------|----------------------|
| Manual typing (`source: manual`) | RapidAPI, top 3 (10 for receipt-normalised queries N/A) | **String matcher** in `matching.py` |
| After receipt scan (`source: receipt`) | RapidAPI, up to **10** candidates per store | **Groq reranker** in `groq_reranker.py` |

Shared steps for both: `detect_search_type()` (brand vs generic), staple expansion for vague words, unit-price comparison when sizes parse, cross-store **Special** inference when the API has no was-price.

**Code:** [`backend/services/compare.py`](backend/services/compare.py), [`backend/services/matching.py`](backend/services/matching.py), [`backend/services/groq_reranker.py`](backend/services/groq_reranker.py).

---

## Product matching

### Branded vs generic (still how it works)

**Decision:** `detect_search_type()` in `matching.py` checks the query against a hardcoded list of **17 brands** (`BRAND_LIST`: a2, Devondale, Bega, etc.). Match is **whole-word** (`\b` regex), so `"bread"` stays generic and `"a2 milk"` is branded.

- **Branded:** only API results whose **name or brand field** contain that brand word are considered. Then the best match is chosen from that filtered list (see string scoring below). If nothing passes the brand filter, that store returns no match.
- **Generic:** e.g. `"milk"`, `"bread"`, `"kirks lemonade"`, or anything not in `BRAND_LIST`. Different brands per store are allowed; the response can note when brands differ. Matcher prefers **homebrand** and **cheapest pack price** among good string matches.

**Note:** This does **not** mean only brands in `BRAND_LIST` can be compared. Most items use the **generic** path. The list only switches on **stricter** rules when we recognise a major brand in the query (so we do not substitute homebrand for a2, Devondale, etc.). Other brand names still work; they are just not locked to that brand name the same way.

**Why:** Branded list items must not swap to homebrand milk. Generic list items are about cheap weekly staples, not forcing the same national brand at both chains.

**Reference:** [`backend/services/matching.py`](backend/services/matching.py) (`detect_search_type`, `_brand_in_query`, `pick_best_match`).

---

### String matching for manual lists

**Decision:** For `source: manual` only, rank candidates with **word-subset boost** (score 0.8 when query words sit in the target text with enough coverage) plus `difflib.SequenceMatcher`. No embeddings. No Groq on this path.

**Branded scoring:** After the brand filter, score each candidate with `max(name_similarity, brand_similarity)` against the **original list line** (not only the expanded search term).

**Generic scoring:** Score **product name only** (never brand). Threshold `GENERIC_SIMILARITY_THRESHOLD = 0.25`. Single-word generics must have at least one query word in the product **name** or the store gets no match.

**Problem we hit:** `"bread"` matched Coles **"Inspired Mud Cake"** because brand was `"Fairy Bread"` and brand score won. Fixed by name-only scoring on the generic path (2026-05-27).

**Reference:** [`backend/services/matching.py`](backend/services/matching.py) (`_similarity_score`, `pick_best_match`).

---

### Strict brand filter (branded only)

**Decision:** If the query contains a known brand but **no** API result has that brand in name or brand field, return `None` for that store instead of guessing.

**Why:** `"a2 milk 2L"` should not fall back to Woolworths homebrand. UI shows no match / no comparison with a clear note.

---

### Staple intent map (generic vague words)

**Decision:** Exact single-word staples in `STAPLE_INTENT_MAP` expand before search (e.g. `"milk"` → `"full cream milk 2L"`). Display text stays the user's word; matching uses the expanded `search_term` for generic scoring.

**Decision (staples at each store):** For generic staples, search with `store_staple_search_term()` so Woolworths gets `"woolworths full cream milk 2L"` and Coles gets `"coles full cream milk 2L"` so own-brand lines show up in API results.

**Why:** `"milk"` alone returns national brands that string-match but are not the cheap line shoppers mean.

**Reference:** [`backend/services/matching.py`](backend/services/matching.py) (`STAPLE_INTENT_MAP`, `expand_staple_query`, `store_staple_search_term`).

---

### Cheapest homebrand preference (generic only)

**Decision:** Among generic candidates above the similarity threshold, prefer items whose name or brand contains a homebrand keyword (`woolworths`, `coles`, `homebrand`, `select`, etc.). From that pool, pick **lowest pack price**. If none qualify, cheapest in the whole passing set.

**Why:** Weekly shop comparison should not pick a2 at $6.90 when the user only typed `"milk"`.

---

### Groq reranker for receipt compares

**Decision:** When `compare_basket(..., source="receipt")`, **do not** use `pick_best_match`. Use `rerank_with_groq()` (`llama-3.1-8b-instant`) on up to 10 candidates per store. Receipt lines are cleaned with `normalize_receipt_search_query()` before search.

**Why:** OCR strings are messy; string match chose wrong products (gravy for Somat, beer for beef).

**Rules in the prompt:** Default **no match** (`-1`) unless type, brand, size, and name line up. Extra produce rules: reject processed/packaged noise, match variety (brown onion not spring onion), still return `-1` if nothing fits.

**Reference:** [`backend/services/groq_reranker.py`](backend/services/groq_reranker.py), [`backend/tests/test_groq_reranker.py`](backend/tests/test_groq_reranker.py).

---

### Unit price normalisation

**Decision:** When both matched products have parseable sizes (`2L`, `700g`, multipack, etc.), item winner and saving use **per 100ml / per 100g**. Otherwise pack price.

**Why:** A 2L vs 1L pack should not call the smaller pack "cheaper" on pack price alone.

**Reference:** [`backend/services/matching.py`](backend/services/matching.py) (`normalise_unit_price`), [`backend/services/compare.py`](backend/services/compare.py) (`_item_winner`).

---

## Pricing, specials, and basket winner

### Basket totals and ties

**Decision:** Overall winner = sum of **pack prices** for items where both stores matched. Tie if Woolworths total vs Coles total within **$0.50** (savings 0). Per-item tie if within 1 cent or 2% relative.

**Decision:** `annualised_savings = weekly savings × 52` for the hero line.

**Why:** Simple story for the banner. Not a "split your shop across two stores" optimiser.

---

### Special badge (`on_special`)

**Decision:** Yellow **Special** badge when `on_special` is true. Two layers:

1. **API (usually inactive):** `was_price` / `original_price` lower than `current_price` in Woolworths/Coles normalisation.
2. **Fallback (what we rely on):** `_infer_cross_store_special()` in `compare.py` when both stores matched same brand + pack size and one price is **≥15%** lower. Marks the cheaper side as on special.

**Caveat:** Fallback is inference (price gap might be permanent, not a promo). Label is **Special**, not "On special".

**Reference:** [`backend/services/compare.py`](backend/services/compare.py), [`frontend/src/components/Results.jsx`](frontend/src/components/Results.jsx).

---

### Specials summary on results hero

**Decision:** Count breakdown rows where `woolworths.on_special` or `coles.on_special` is true. Show e.g. `3 items on special at Woolworths · 1 at Coles` under annualised savings. Hide if both counts are zero.

**Reference:** [`frontend/src/components/Results.jsx`](frontend/src/components/Results.jsx).

---

## Receipt and compare flow

### Google Gemini for receipt OCR

**Decision:** Receipt images → `gemini-2.5-flash`; JSON array of item strings. Parse strips markdown fences. Empty list on failure, not a 500.

**Reference:** [`backend/services/receipt.py`](backend/services/receipt.py).

---

### Receipt scan, then manual review

**Decision:** Upload only runs OCR. Items fill **Build list**; user edits, then **Compare**. `source: 'receipt'` until **Clear list** (edits alone keep receipt source for Groq).

**Reference:** [`frontend/src/components/ReceiptUpload.jsx`](frontend/src/components/ReceiptUpload.jsx), [`frontend/src/App.jsx`](frontend/src/App.jsx).

---

## Frontend (selected)

### View state in `App.jsx` (no React Router)

**Decision:** `view`: `list` | `loading` | `results` | `error`. Linear SPA, no URL routes.

---

### Product links in breakdown

**Decision:** `url` from RapidAPI through to `StoreProduct`. **View on Woolworths / Coles** when non-empty; `target="_blank"`, `rel="noopener noreferrer"`.

---

### Error handling

**Frontend:** Compare failure → `error` view with list kept. Receipt errors inline on the upload tab. [`frontend/src/lib/api.js`](frontend/src/lib/api.js) reads `detail` from error JSON responses.

**Backend `/api/compare`** ([`backend/routers/compare.py`](backend/routers/compare.py)): specific handlers before a last-resort 500. Client messages are generic; full errors go to server logs only.

| Upstream failure | HTTP | `detail` (client) |
|------------------|------|-------------------|
| RapidAPI timeout | 504 | Store price lookup timed out. Try again. |
| RapidAPI connection failure | 503 | Unable to reach store price service. Try again. |
| RapidAPI HTTP error or other request error | 502 | Store price lookup failed. Try again. |
| Invalid JSON from store API | 502 | Store returned invalid data. Try again. |
| Groq rerank failure (`source: receipt`) | 502 | Product matching unavailable. Try again. |
| Anything else unexpected | 500 | Comparison failed. Try again later. |

**Backend `/api/receipt`** ([`backend/routers/receipt.py`](backend/routers/receipt.py)):

| Upstream failure | HTTP | `detail` (client) |
|------------------|------|-------------------|
| Gemini overloaded (503) | 503 | Receipt scanner is busy. Please try again in a moment. |
| Invalid base64 image | 400 | Invalid receipt image encoding. |
| Other Gemini server errors | 502 | Gemini error text (`str(exc)`) |
| Gemini client error | 502 | Receipt scanner could not process this image. |
| Anything else unexpected | 500 | Receipt scan failed. Please try again. |

**Service layer:** [`backend/services/receipt.py`](backend/services/receipt.py) returns an empty item list when Gemini is unavailable or parsing fails (no 500 for OCR miss). [`backend/services/groq_reranker.py`](backend/services/groq_reranker.py) logs and re-raises `GroqAPIError` so the compare router can map it.

**Reference:** [`backend/tests/test_compare_router.py`](backend/tests/test_compare_router.py) for compare HTTP mapping tests.

---

## Data and backend operations

### Live RapidAPI for both stores

**Decision:** One `RAPIDAPI_KEY`, `page_size=3` default (10 for receipt searches). Pick best match from results, not always rank 1.

---

### In-memory search cache

**Decision:** Cache key `(store, normalised_query, page_size)`, TTL default 900s (`SEARCH_CACHE_TTL_SECONDS`).

**Reference:** [`backend/services/cache.py`](backend/services/cache.py).

---

### Parallel searches

**Decision:** Woolworths + Coles in parallel per item; up to 5 items in parallel across the basket.

**Reference:** [`backend/services/compare.py`](backend/services/compare.py).

---

### Rate limiting and health

**Decision:** `/api/*` limited to 30 req/min/IP by default (`RATE_LIMIT_PER_MINUTE`). `GET /health` → `{"status":"ok"}`, not rate limited.

**Reference:** [`backend/services/rate_limit.py`](backend/services/rate_limit.py), [`backend/main.py`](backend/main.py).

---

### Gated API debug logs

**Decision:** Extra RapidAPI debug log lines (result counts and truncated query) only if `DEBUG_API_RESPONSES=true`. Full JSON bodies are not logged.

---

## Architecture

### Vite + React (not Next.js)

**Decision:** Stay on Vite SPA. No SEO need; FastAPI stays the API boundary.

---

### FastAPI + server-side keys

**Decision:** All store and LLM calls server-side. Frontend hits `/api/compare` and `/api/receipt` only.

---

## Testing

**Decision:** `test_compare.py`, `test_compare_router.py`, and `test_matching.py` with mocked APIs; `test_cache.py`, `test_rate_limit.py`, `test_groq_reranker.py`, `test_receipt_parse.py`. **51** pytest tests total; GitHub Actions runs them on push.

---

## How to extend this file

1. Add a subsection under the closest heading (or create one).
2. **Decision**, **Why**, and any bug/fix note.
3. Link to code where it helps.

Do not use em dashes in this file (project convention).
