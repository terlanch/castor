"""File download endpoints (public – no auth required)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse

from ....config import UPLOADS_DIR
from ....database import get_store

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/{file_id}")
def download_file(file_id: str):
    """Download a previously uploaded file by its ID.

    The response includes proper Content-Disposition headers so the browser
    will prompt a download with the original filename.
    """
    store = get_store()
    meta = store.get_uploaded_file(file_id)
    if not meta:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found.")

    # Locate the file on disk
    task_dir = UPLOADS_DIR / meta.task_id
    # Find the actual file (file_id + extension)
    candidates = list(task_dir.glob(f"{file_id}*")) if task_dir.is_dir() else []
    if not candidates:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File data missing from disk.")

    disk_path = candidates[0]
    return FileResponse(
        path=str(disk_path),
        media_type=meta.content_type,
        filename=meta.original_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{meta.original_filename}"',
        },
    )


@router.get("/{file_id}/info", response_class=JSONResponse)
def file_info(file_id: str):
    """Get metadata about an uploaded file (no download)."""
    store = get_store()
    meta = store.get_uploaded_file(file_id)
    if not meta:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found.")
    return meta.model_dump(mode="json")
