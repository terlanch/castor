"""Matching / tags public endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .taxonomy import TAG_DIMENSIONS

router = APIRouter(tags=["Matching"])


@router.get("/tags", response_class=JSONResponse)
def list_tag_taxonomy():
    """Return the standardised tag dictionary for reference."""
    return {"dimensions": TAG_DIMENSIONS}
