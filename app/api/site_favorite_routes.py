from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.crud import FavoriteCRUD, UserCRUD
from app.api.schemas import FavoriteCreate
from app.auth.dependencies import get_current_site_user
from app.auth.mongo import get_auth_users_collection
from app.auth.schemas import SiteUserPublic
from app.auth.service import resolve_user_identifier
from app.auth.telegram_sync import sync_telegram_user_from_site
from app.database.connection import get_db

router = APIRouter(prefix="/site/favorites", tags=["Site Favorites"])


def _serialize_favorite_date(value: datetime | None) -> str:
    return (value or datetime.utcnow()).isoformat()


def _normalize_site_favorite(entry: dict[str, Any]) -> dict[str, Any] | None:
    product_id = str(entry.get("product_id") or "").strip()
    if not product_id:
        return None

    region = entry.get("region")
    if isinstance(region, str):
        region = region.strip().upper() or None
    else:
        region = None

    added_at = entry.get("added_at")
    if not isinstance(added_at, datetime):
        added_at = datetime.utcnow()

    return {
        "product_id": product_id,
        "region": region,
        "added_at": added_at,
    }


def _serialize_favorite_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": entry["product_id"],
        "region": entry.get("region"),
        "added_at": _serialize_favorite_date(entry.get("added_at")),
    }


def _get_site_user_doc(current_user: SiteUserPublic) -> dict[str, Any] | None:
    return get_auth_users_collection().find_one({"_id": resolve_user_identifier(current_user.id)})


def _get_site_favorites(current_user: SiteUserPublic) -> list[dict[str, Any]]:
    user_doc = _get_site_user_doc(current_user)
    raw_favorites = user_doc.get("favorite_products", []) if user_doc else []
    if not isinstance(raw_favorites, list):
        return []

    favorites: list[dict[str, Any]] = []
    seen_product_ids: set[str] = set()
    for raw_entry in raw_favorites:
        if not isinstance(raw_entry, dict):
            continue
        entry = _normalize_site_favorite(raw_entry)
        if not entry or entry["product_id"] in seen_product_ids:
            continue
        seen_product_ids.add(entry["product_id"])
        favorites.append(entry)

    favorites.sort(key=lambda item: item.get("added_at") or datetime.min, reverse=True)
    return favorites


def _save_site_favorites(current_user: SiteUserPublic, favorites: list[dict[str, Any]]) -> None:
    get_auth_users_collection().update_one(
        {"_id": resolve_user_identifier(current_user.id)},
        {
            "$set": {
                "favorite_products": favorites,
                "updated_at": datetime.utcnow(),
            }
        },
    )


def _resolve_legacy_user(db: Session, current_user: SiteUserPublic):
    if current_user.telegram_id is None:
        raise HTTPException(status_code=422, detail={"message": "Синхронизация избранного через Telegram недоступна для этого аккаунта."})

    sync_telegram_user_from_site(
        db=db,
        users_collection=get_auth_users_collection(),
        site_user_id=current_user.id,
    )

    legacy_user = UserCRUD.get_by_telegram_id(db, current_user.telegram_id)
    if not legacy_user:
        raise HTTPException(status_code=404, detail={"message": "Telegram-профиль для избранного не найден."})

    return legacy_user


def _try_resolve_legacy_user(db: Session, current_user: SiteUserPublic):
    if current_user.telegram_id is None:
        return None

    return _resolve_legacy_user(db, current_user)


@router.get("", response_model=list[dict], summary="Список избранного для Telegram-пользователя сайта")
async def list_site_favorites(
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    site_favorites = _get_site_favorites(current_user)
    merged_by_product_id = {entry["product_id"]: entry for entry in site_favorites}

    legacy_user = _try_resolve_legacy_user(db, current_user)
    if legacy_user:
        for favorite in FavoriteCRUD.get_user_favorites(db, legacy_user.id):
            entry = {
                "product_id": favorite.product_id,
                "region": favorite.region,
                "added_at": favorite.created_at,
            }
            current = merged_by_product_id.get(favorite.product_id)
            if not current or (entry["added_at"] or datetime.min) > (current.get("added_at") or datetime.min):
                merged_by_product_id[favorite.product_id] = entry

    merged = sorted(merged_by_product_id.values(), key=lambda item: item.get("added_at") or datetime.min, reverse=True)
    if merged != site_favorites:
        _save_site_favorites(current_user, merged)

    return [_serialize_favorite_entry(entry) for entry in merged]


@router.post("", response_model=dict, summary="Добавить товар в Telegram-избранное сайта")
async def add_site_favorite(
    payload: FavoriteCreate,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    product_id = payload.product_id.strip()
    region = payload.region.strip().upper() if payload.region else None
    favorites = [entry for entry in _get_site_favorites(current_user) if entry["product_id"] != product_id]
    favorites.insert(0, {"product_id": product_id, "region": region, "added_at": datetime.utcnow()})
    _save_site_favorites(current_user, favorites)

    legacy_user = _try_resolve_legacy_user(db, current_user)
    if legacy_user:
        favorite = FavoriteCRUD.add_to_favorites(db, legacy_user.id, product_id, region)
        added_at = favorite.created_at
    else:
        added_at = favorites[0]["added_at"]

    return {
        "product_id": product_id,
        "region": region,
        "added_at": _serialize_favorite_date(added_at),
    }


@router.delete("/{product_id}", response_model=dict, summary="Удалить товар из Telegram-избранного сайта")
async def remove_site_favorite(
    product_id: str,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    favorites = [entry for entry in _get_site_favorites(current_user) if entry["product_id"] != product_id]
    _save_site_favorites(current_user, favorites)

    legacy_user = _try_resolve_legacy_user(db, current_user)
    if legacy_user:
        FavoriteCRUD.remove_from_favorites(db, legacy_user.id, product_id)
    return {"message": "Товар удалён из избранного."}
