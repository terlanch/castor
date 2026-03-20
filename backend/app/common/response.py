"""Standard response helpers."""
from __future__ import annotations

from fastapi.responses import JSONResponse


def success(data: dict | list | None = None, **extra) -> JSONResponse:
    body: dict = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return JSONResponse(body)
