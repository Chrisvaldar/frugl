import logging
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException
from groq import APIError as GroqAPIError
from pydantic import BaseModel

from services.compare import compare_basket

logger = logging.getLogger(__name__)

router = APIRouter()


class CompareRequest(BaseModel):
    items: list[str]
    receipt_text: Optional[str] = None
    source: Optional[str] = "manual"


@router.post("/compare")
def compare(request: CompareRequest):
    try:
        source = request.source or "manual"
        return compare_basket(request.items, source=source)
    except requests.Timeout as exc:
        logger.error("Store lookup timed out")
        raise HTTPException(
            status_code=504,
            detail="Store price lookup timed out. Try again.",
        ) from exc
    except requests.ConnectionError as exc:
        logger.error("Store lookup connection failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to reach store price service. Try again.",
        ) from exc
    except requests.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", "unknown")
        logger.error("Store lookup HTTP error: %s", status)
        raise HTTPException(
            status_code=502,
            detail="Store price lookup failed. Try again.",
        ) from exc
    except requests.RequestException as exc:
        logger.exception("Store lookup failed")
        raise HTTPException(
            status_code=502,
            detail="Store price lookup failed. Try again.",
        ) from exc
    except ValueError as exc:
        logger.exception("Store returned invalid data")
        raise HTTPException(
            status_code=502,
            detail="Store returned invalid data. Try again.",
        ) from exc
    except GroqAPIError as exc:
        logger.exception("Groq product matching failed")
        raise HTTPException(
            status_code=502,
            detail="Product matching unavailable. Try again.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected comparison error")
        raise HTTPException(
            status_code=500,
            detail="Comparison failed. Try again later.",
        ) from exc
