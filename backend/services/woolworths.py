import logging
import os

import requests

from services.cache import get_cached_search, set_cached_search
from services.log_util import truncate

logger = logging.getLogger(__name__)

WOOLWORTHS_SEARCH_URL = (
    "https://woolworths-products-api.p.rapidapi.com/woolworths/product-search/"
)
RAPIDAPI_HOST = "woolworths-products-api.p.rapidapi.com"


def _debug_api_responses() -> bool:
    return os.getenv("DEBUG_API_RESPONSES", "").lower() in ("true", "1", "yes")


def _on_special(item: dict, current_price: float) -> bool:
    was_price = item.get("was_price")
    if was_price is None:
        was_price = item.get("original_price")
    if was_price is None:
        return False
    try:
        return current_price < float(was_price)
    except (TypeError, ValueError):
        return False


def search_item(query: str, page_size: int = 3) -> list[dict]:
    """Search Woolworths catalog; return up to page_size normalized product dicts."""
    cached = get_cached_search("woolworths", query, page_size)
    if cached is not None:
        logger.debug("Woolworths cache hit (page_size=%d)", page_size)
        return cached

    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            WOOLWORTHS_SEARCH_URL,
            params={"query": query, "page_size": page_size},
            headers={
                "x-rapidapi-host": RAPIDAPI_HOST,
                "x-rapidapi-key": api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        result_count = len(data.get("results", []))
        logger.debug("Woolworths search returned %d result(s)", result_count)
        if _debug_api_responses():
            logger.debug(
                "Woolworths API debug payload (%d result(s), query %s)",
                result_count,
                truncate(query),
            )
    except (requests.RequestException, ValueError):
        logger.exception("Woolworths search failed (query %s)", truncate(query))
        raise

    results = []
    for item in data.get("results", [])[:page_size]:
        current_price = float(item.get("current_price", 0))
        results.append(
            {
                "name": item.get("product_name", ""),
                "brand": item.get("product_brand", ""),
                "price": current_price,
                "size": item.get("product_size", ""),
                "url": item.get("url") or "",
                "on_special": _on_special(item, current_price),
            }
        )

    set_cached_search("woolworths", query, page_size, results)
    return results
