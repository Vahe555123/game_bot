from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.crud import FavoriteCRUD
from app.api.schemas import FavoriteCreate
from app.auth.dependencies import get_current_site_user
from app.auth.schemas import SiteUserPublic
from app.auth.service import resolve_user_identifier
from app.database.connection import get_db
from app.utils.time import utcnow

router = APIRouter(prefix="/site/favorites", tags=["Site Favorites"])


def _serialize_favorite_date(value: datetime | None) -> str:
    return (value or utcnow()).isoformat()


def _resolve_site_user_id(current_user: SiteUserPublic) -> int:
    resolved_user_id = resolve_user_identifier(current_user.id)
    if not isinstance(resolved_user_id, int):
        raise HTTPException(status_code=422, detail={"message": "Некорректный идентификатор пользователя."})
    return resolved_user_id


def _serialize_favorite_entry(entry) -> dict[str, str | None]:
    return {
        "product_id": entry.product_id,
        "region": entry.region,
        "added_at": _serialize_favorite_date(entry.created_at),
    }


@router.get("", response_model=list[dict], summary="Список избранного для Telegram-пользователя сайта")
async def list_site_favorites(
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    favorites = FavoriteCRUD.get_user_favorites(db, _resolve_site_user_id(current_user))
    favorites.sort(key=lambda item: item.created_at or datetime.min, reverse=True)
    return [_serialize_favorite_entry(entry) for entry in favorites]


@router.post("", response_model=dict, summary="Добавить товар в Telegram-избранное сайта")
async def add_site_favorite(
    payload: FavoriteCreate,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    product_id = payload.product_id.strip()
    region = payload.region.strip().upper() if payload.region else None
    favorite = FavoriteCRUD.add_to_favorites(db, _resolve_site_user_id(current_user), product_id, region)
    if not favorite:
        raise HTTPException(status_code=404, detail="Товар не найден")

    return {
        "product_id": product_id,
        "region": region,
        "added_at": _serialize_favorite_date(favorite.created_at),
    }


@router.delete("/{product_id}", response_model=dict, summary="Удалить товар из Telegram-избранного сайта")
async def remove_site_favorite(
    product_id: str,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    FavoriteCRUD.remove_from_favorites(db, _resolve_site_user_id(current_user), product_id)
    return {"message": "Товар удалён из избранного."}
