import json
import logging
import os

import requests

from services.cache import get_cached_search, set_cached_search

logger = logging.getLogger(__name__)

COLES_SEARCH_URL = (
    "https://coles-product-price-api.p.rapidapi.com/coles/product-search/"
)
RAPIDAPI_HOST = "coles-product-price-api.p.rapidapi.com"


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
    """Search Coles catalog; return up to page_size normalized product dicts."""
    cached = get_cached_search("coles", query, page_size)
    if cached is not None:
        print(f"[Coles API] cache hit query={query!r}")
        return cached

    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            COLES_SEARCH_URL,
            params={"query": query, "page_size": page_size},
            headers={
                "x-rapidapi-host": RAPIDAPI_HOST,
                "x-rapidapi-key": api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        print(f"[Coles API] query={query!r}")
        if _debug_api_responses():
            print(json.dumps(data, indent=2))
    except (requests.RequestException, ValueError):
        logger.exception("Coles search failed for query=%r", query)
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

    set_cached_search("coles", query, page_size, results)
    return results
