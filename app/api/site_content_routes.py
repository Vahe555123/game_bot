from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.auth.exceptions import AuthServiceError
from app.site_admin.schemas import AdminHelpContentResponse
from app.site_admin.service import get_site_admin_service

router = APIRouter(prefix="/site/content", tags=["Site Content"])


def _raise_http_auth_error(error: AuthServiceError) -> None:
    detail = {"message": error.message}
    detail.update(error.extra)
    raise HTTPException(status_code=error.status_code, detail=detail)


@router.get("/help", response_model=AdminHelpContentResponse, summary="Public help page content")
def get_help_page_content():
    service = get_site_admin_service()
    try:
        return service.get_help_content()
    except AuthServiceError as error:
        _raise_http_auth_error(error)
