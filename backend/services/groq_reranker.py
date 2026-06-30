import logging
import os
import re

from groq import Groq

logger = logging.getLogger(__name__)

RERANK_MODEL = "llama-3.1-8b-instant"

PRODUCE_KEYWORDS = (
    "onion",
    "cabbage",
    "tomato",
    "rockmelon",
    "apple",
    "banana",
    "carrot",
    "broccoli",
    "chicken",
    "beef",
    "pork",
    "lamb",
    "mince",
    "melon",
    "potato",
    "lettuce",
    "capsicum",
    "zucchini",
    "mushroom",
    "pear",
    "orange",
    "lemon",
    "lime",
    "grape",
    "strawberry",
    "blueberry",
    "mango",
    "avocado",
    "spinach",
    "celery",
    "pumpkin",
    "sweet potato",
    "corn",
    "peas",
    "beans",
    "asparagus",
    "cauliflower",
    "kale",
    "herbs",
    "garlic",
    "ginger",
    "steak",
    "fillet",
    "sausage",
    "bacon",
    "ham",
    "turkey",
    "duck",
    "salmon",
    "prawn",
    "fish",
)


def is_produce_query(query: str) -> bool:
    """Return True when the query looks like fresh fruit, vegetable, or meat."""
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in PRODUCE_KEYWORDS)


def _format_candidate(index: int, item: dict) -> str:
    return (
        f"{index}: {item.get('name', '')} | {item.get('brand', '')} | "
        f"{item.get('size', '')} | ${item.get('price', '')}"
    )


def _produce_rules_block() -> str:
    return (
        "FRESH PRODUCE RULES (this query is fresh produce):\n"
        "- Reject candidates that are clearly processed or packaged: anything containing "
        "gravy, mix, tin, sauce, wine, frozen, powder, broth, soup, pet, dog.\n"
        "- Require the same variety: if query says 'green cabbage' reject wombok, savoy, "
        "red cabbage; if query says 'brown onion' reject spring onion, shallot.\n"
        "- Word order may differ and loose/each/kg is fine (e.g. brown onions → Onion Brown each).\n"
        "- If no candidate clearly matches the fresh produce type AND variety, return -1.\n\n"
    )


def _build_prompt(query: str, candidate_lines: str, max_index: int) -> str:
    produce_rules = _produce_rules_block() if is_produce_query(query) else ""

    return (
        "You are a strict grocery product matcher for Australian supermarket receipts.\n"
        "Your job is to REJECT bad matches. Only accept a candidate when it is clearly "
        "the same product as the receipt line.\n"
        "When in doubt, return -1.\n\n"
        f"{produce_rules}"
        "Return -1 unless ALL of these are true for one candidate:\n"
        "1. Same product TYPE (peas not onion rings, beef mince not pies or dog food, "
        "dishwashing tablets not denture tablets or medicine, brioche bagels not blueberry bagels, "
        "fresh tomatoes not soup or arancini).\n"
        "2. Same or very similar BRAND when the receipt names a brand "
        "(Somat, McCain, Abe's, etc.). Different brand = -1.\n"
        "3. Same or very similar SIZE/weight when the receipt includes one "
        "(500g not 2kg, 360g not 300g unless clearly the same pack). Large size mismatch = -1.\n"
        "4. The product name describes the same item, not just one shared word "
        "(shared word 'beef', 'frozen', 'tablets', or '4' alone is NOT enough).\n\n"
        "Always return -1 for:\n"
        "- Pet food, beer, medicine, denture products, tanning products, unrelated categories\n"
        "- Different flavour or variant (brioche vs blueberry, supergrain vs brioche)\n"
        "- Store name on receipt (COLES/WOOLWORTHS) does NOT mean match any Coles/Woolworths product\n"
        "- Only vague or partial overlap\n"
        "- You would not confidently buy this candidate based on the receipt line\n\n"
        f"Return ONLY a single integer: index 0-{max_index} for ONE clear match, "
        "or -1 if no candidate is a clear match.\n"
        "No explanation, just the number.\n"
        f"Receipt item: {query}\n"
        f"Candidates:\n{candidate_lines}"
    )


def rerank_with_groq(query: str, candidates: list[dict]) -> dict | None:
    """Pick the best API candidate for a receipt line, or None if no good match."""
    print(f"[rerank_with_groq] called query={query!r} candidates={len(candidates)}")
    print(f"[rerank_with_groq] is_produce_query={is_produce_query(query)}")
    for index, item in enumerate(candidates):
        print(f"[rerank_with_groq]   {_format_candidate(index, item)}")

    if not candidates:
        print("[rerank_with_groq] skipping — no candidates")
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[rerank_with_groq] skipping — GROQ_API_KEY not set")
        return None

    candidate_lines = "\n".join(
        _format_candidate(index, item) for index, item in enumerate(candidates)
    )
    max_index = len(candidates) - 1
    prompt = _build_prompt(query, candidate_lines, max_index)

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=RERANK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict product matcher. Default to -1. "
                        "Only output a valid index when the match is obvious."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        print(f"[rerank_with_groq] raw Groq response={text!r}")
        match = re.search(r"-?\d+", text)
        if not match:
            print("[rerank_with_groq] no integer found in response")
            return None

        index = int(match.group())
        print(f"[rerank_with_groq] parsed index={index}")
        if index == -1:
            print("[rerank_with_groq] Groq rejected all candidates")
            return None
        if 0 <= index < len(candidates):
            selected = candidates[index]
            print(
                "[rerank_with_groq] selected "
                f"{_format_candidate(index, selected)}"
            )
            return selected
        print(f"[rerank_with_groq] index out of range: {index}")
    except Exception:
        logger.exception("Groq rerank failed for query=%r", query)
        raise

    return None
