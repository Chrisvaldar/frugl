import logging
from concurrent.futures import ThreadPoolExecutor

from services.groq_reranker import rerank_with_groq
from services.woolworths import search_item as search_woolworths
from services.coles import search_item as search_coles
from services.matching import (
    detect_search_type,
    expand_staple_query,
    filter_comparable_items,
    is_staple_query,
    normalize_receipt_search_query,
    pick_best_match,
    normalise_unit_price,
    store_staple_search_term,
)

logger = logging.getLogger(__name__)

RECEIPT_CANDIDATE_LIMIT = 10
MAX_CONCURRENT_ITEMS = 5


def _infer_cross_store_special(
    w_result: dict | None, c_result: dict | None
) -> None:
    """Infer on_special when the API omits was/original price but one store is much cheaper."""
    if not w_result or not c_result:
        return

    w_brand = (w_result.get("brand") or "").strip().lower()
    c_brand = (c_result.get("brand") or "").strip().lower()
    w_size = (w_result.get("size") or "").strip().lower()
    c_size = (c_result.get("size") or "").strip().lower()
    if not w_brand or w_brand != c_brand or w_size != c_size:
        return

    w_price = w_result["price"]
    c_price = c_result["price"]
    if w_price <= 0 or c_price <= 0:
        return

    cheaper_ratio = min(w_price, c_price) / max(w_price, c_price)
    if cheaper_ratio > 0.85:
        return

    if w_price < c_price and not w_result.get("on_special"):
        w_result["on_special"] = True
    elif c_price < w_price and not c_result.get("on_special"):
        c_result["on_special"] = True


def _build_store_result(match: dict | None) -> dict | None:
    """Convert a raw API result into the standardised store result shape."""
    if match is None:
        return None

    price = match.get("price") or 0.0
    size = match.get("size") or ""
    normalised = normalise_unit_price(price, size)

    return {
        "name": match.get("name") or "",
        "brand": match.get("brand") or "",
        "price": price,
        "size": size,
        "unit_price": normalised[0] if normalised else None,
        "unit": normalised[1] if normalised else None,
        "url": match.get("url") or "",
        "on_special": match.get("on_special") or False,
        "confidence": _confidence(match),
    }


def _confidence(match: dict) -> str:
    """Derive a confidence label from the match score if present, else 'medium'."""
    score = match.get("_score")
    if score is None:
        return "medium"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _item_winner(w_result: dict | None, c_result: dict | None) -> tuple[str, float]:
    """
    Determine the winner for a single item.
    Returns (winner, saving) where saving is always >= 0.
    Uses unit_price for comparison when both are available, else pack price.
    """
    if w_result is None and c_result is None:
        return "no_comparison", 0.0
    if w_result is None:
        return "no_comparison", 0.0
    if c_result is None:
        return "no_comparison", 0.0

    w_unit = w_result["unit_price"]
    c_unit = c_result["unit_price"]
    both_have_unit_price = w_unit is not None and c_unit is not None

    # Prefer unit price for winner when both available; else pack price
    if both_have_unit_price:
        w_compare = w_unit
        c_compare = c_unit
    else:
        w_compare = w_result["price"]
        c_compare = c_result["price"]

    diff = abs(w_compare - c_compare)

    # Tie threshold — within 2% of each other or less than 1 cent per 100ml/g
    if diff < 0.01 or (max(w_compare, c_compare) > 0 and diff / max(w_compare, c_compare) < 0.02):
        return "tie", 0.0

    if w_compare < c_compare:
        winner = "woolworths"
    else:
        winner = "coles"

    # Unit-price saving when both normalised; otherwise pack price difference
    if both_have_unit_price:
        saving = round(abs(w_unit - c_unit), 4)
    else:
        saving = round(abs(w_result["price"] - c_result["price"]), 2)

    return winner, saving


def _build_note(
    search_type: str,
    w_result: dict | None,
    c_result: dict | None,
    winner: str,
) -> str | None:
    """Generate a human-readable note about the comparison quality."""
    if winner == "no_comparison":
        if w_result is None and c_result is None:
            return "No match found at either store"
        if w_result is None:
            return "Not available at Woolworths"
        if c_result is None:
            return "Not available at Coles"

    if search_type == "generic" and w_result and c_result:
        w_brand = (w_result.get("brand") or "").lower()
        c_brand = (c_result.get("brand") or "").lower()
        if w_brand and c_brand and w_brand != c_brand:
            return "Different brands — comparing unit price where possible"

    if w_result and c_result:
        w_size = (w_result.get("size") or "").lower()
        c_size = (c_result.get("size") or "").lower()
        if w_size and c_size and w_size != c_size:
            return f"Different pack sizes ({w_result['size']} vs {c_result['size']}) — comparing per unit price"

    return None


def _search_both_stores(
    woolworths_query: str,
    coles_query: str,
    page_size: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Run Woolworths and Coles searches concurrently for one item."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        woolworths_future = executor.submit(search_woolworths, woolworths_query, page_size)
        coles_future = executor.submit(search_coles, coles_query, page_size)
        return woolworths_future.result(), coles_future.result()


def _fetch_raw_results(
    item: str, source: str, search_type: str
) -> tuple[str, list[dict], list[dict]]:
    """Fetch store search results for a single list item."""
    if source == "receipt":
        search_term = normalize_receipt_search_query(item)
        w_raw, c_raw = _search_both_stores(
            search_term, search_term, page_size=RECEIPT_CANDIDATE_LIMIT
        )
        return search_term, w_raw, c_raw

    if search_type == "generic" and is_staple_query(item):
        search_term = expand_staple_query(item)
        w_raw, c_raw = _search_both_stores(
            store_staple_search_term(search_term, "woolworths"),
            store_staple_search_term(search_term, "coles"),
        )
        return search_term, w_raw, c_raw

    search_term = expand_staple_query(item)
    w_raw, c_raw = _search_both_stores(search_term, search_term)
    return search_term, w_raw, c_raw


def _process_single_item(item: str, source: str) -> dict:
    """Compare one list item across Woolworths and Coles."""
    search_type = detect_search_type(item)
    search_term, w_raw, c_raw = _fetch_raw_results(item, source, search_type)

    if source == "receipt":
        w_match = rerank_with_groq(item, w_raw) if w_raw else None
        c_match = rerank_with_groq(item, c_raw) if c_raw else None
    else:
        w_match = pick_best_match(item, w_raw, search_type, search_term=search_term)
        c_match = pick_best_match(item, c_raw, search_type, search_term=search_term)

    if w_match is None and c_match is None:
        return {
            "item": item,
            "match_type": "no_match",
            "woolworths": None,
            "coles": None,
            "winner": "no_comparison",
            "saving": 0.0,
            "note": "No match found at either store",
        }

    w_result = _build_store_result(w_match)
    c_result = _build_store_result(c_match)
    _infer_cross_store_special(w_result, c_result)

    match_type = "branded" if search_type == "branded" else "generic"
    winner, saving = _item_winner(w_result, c_result)
    note = _build_note(search_type, w_result, c_result, winner)

    return {
        "item": item,
        "match_type": match_type,
        "woolworths": w_result,
        "coles": c_result,
        "winner": winner,
        "saving": saving,
        "note": note,
    }


def compare_basket(items: list[str], source: str = "manual") -> dict:
    """Compare a shopping list across Woolworths and Coles."""
    items = filter_comparable_items(items)
    logger.info("Comparing basket: source=%s items=%d", source, len(items))
    if not items:
        return {
            "winner": "tie",
            "total_woolworths": 0.0,
            "total_coles": 0.0,
            "savings": 0.0,
            "annualised_savings": 0.0,
            "breakdown": [],
        }

    max_workers = min(MAX_CONCURRENT_ITEMS, len(items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        breakdown = list(executor.map(lambda item: _process_single_item(item, source), items))

    total_woolworths = 0.0
    total_coles = 0.0
    for row in breakdown:
        if row["woolworths"] and row["winner"] != "no_comparison":
            total_woolworths += row["woolworths"]["price"]
        if row["coles"] and row["winner"] != "no_comparison":
            total_coles += row["coles"]["price"]

    diff = total_woolworths - total_coles
    if abs(diff) <= 0.50:
        overall_winner = "tie"
        overall_savings = 0.0
    elif diff < 0:
        overall_winner = "woolworths"
        overall_savings = round(abs(diff), 2)
    else:
        overall_winner = "coles"
        overall_savings = round(abs(diff), 2)

    return {
        "winner": overall_winner,
        "total_woolworths": round(total_woolworths, 2),
        "total_coles": round(total_coles, 2),
        "savings": overall_savings,
        "annualised_savings": round(overall_savings * 52, 2),
        "breakdown": breakdown,
    }
