import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
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
    except Exception as e:
        logger.exception("Unexpected comparison error")
        raise HTTPException(status_code=500, detail="Comparison failed. Try again later") from e
