import base64
import json
import logging
import os
import re
import time

from google import genai
from google.genai import types
from google.genai.errors import ServerError

from services.log_util import truncate
from services.matching import filter_comparable_items

logger = logging.getLogger(__name__)

RECEIPT_MODEL = "gemini-2.5-flash"
MAX_GEMINI_RETRIES = 3
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)

PROMPT = """Extract grocery items from this receipt. Return a JSON array of search-friendly product names. Follow these rules:

Remove store names, weights from item names (e.g. WOOLWORTHS, COLES prefix)
For produce/fresh items, convert receipt abbreviations to natural search terms: ONION BROWN 1KG → brown onions, CABBAGE GRN HALF → green cabbage half, TOMATOES PERKG → gourmet tomatoes, MELON ROCKMELON → rockmelon
For branded items, keep brand name and size: MCCAINS FROZEN PEAS 500G → McCain frozen peas 500g
Remove quantity/weight suffixes that are per-kg prices (PERKG, NET @)
Include all product lines (food, cleaning, pest control, stationery, etc.); skip non-product lines like subtotals, payment details, and store bag charges (reusable bag, shopping bag, carry bag, plastic bag)
Return only the JSON array, no markdown, no backticks"""


def _normalize_base64(image_base64: str) -> str:
    """Strip whitespace and data-URL prefix if present."""
    value = image_base64.strip()
    if value.startswith("data:") and "," in value:
        value = value.split(",", 1)[1]
    return value


def _normalize_mime_type(mime_type: str) -> str:
    """Normalize browser MIME aliases to values Gemini accepts."""
    value = mime_type.strip().lower()
    if value == "image/jpg":
        return "image/jpeg"
    if value == "image/heif":
        return "image/heic"
    return value or "image/jpeg"


def _normalize_json_text(text: str) -> str:
    """Strip markdown fences and normalize common Gemini JSON quirks."""
    value = text.strip()
    if not value:
        return value

    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value).strip()

    value = (
        value.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    value = re.sub(r",(\s*])", r"\1", value)
    return value


def _parse_items_json(text: str) -> list[str]:
    """Parse Gemini output into a list of item strings."""
    value = _normalize_json_text(text)
    if not value:
        return []

    def load_array(raw: str) -> list[str] | None:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(items, list):
            return [str(item).strip() for item in items if str(item).strip()]
        return None

    parsed = load_array(value)
    if parsed is not None:
        return parsed

    array_match = re.search(r"\[[\s\S]*\]", value)
    if array_match:
        parsed = load_array(array_match.group())
        if parsed is not None:
            return parsed

    logger.warning(
        "Receipt JSON parse failed (response %s)",
        truncate(text),
    )
    return []


def extract_items_from_receipt(
    image_base64: str, mime_type: str = "image/jpeg"
) -> list[str]:
    """Extract grocery item names from a receipt image via Gemini vision."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not image_base64:
        return []

    image_data = base64.b64decode(_normalize_base64(image_base64))
    response = None

    with genai.Client(api_key=api_key) as client:
        for attempt in range(MAX_GEMINI_RETRIES):
            try:
                response = client.models.generate_content(
                    model=RECEIPT_MODEL,
                    contents=[
                        PROMPT,
                        types.Part.from_bytes(
                            data=image_data,
                            mime_type=_normalize_mime_type(mime_type),
                        ),
                    ],
                )
                break
            except ServerError as exc:
                if exc.code == 503 and attempt < MAX_GEMINI_RETRIES - 1:
                    delay = RETRY_BACKOFF_SECONDS[attempt]
                    logger.info(
                        "Gemini 503, retry %d/%d in %ss",
                        attempt + 1,
                        MAX_GEMINI_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                logger.error("Gemini extraction failed with code %s", exc.code)
                raise

    text = (response.text or "").strip()
    items = _parse_items_json(text)
    items = filter_comparable_items(items)
    logger.info("Receipt extraction parsed %d item(s)", len(items))
    return items
