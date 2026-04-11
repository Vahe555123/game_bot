from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from sqlalchemy.orm import Session

from app.api.crud import UserCRUD
from app.models.psn_account import PSNAccount
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.utcnow()


def _resolve_site_user_id(user_id: Any) -> Any:
    if isinstance(user_id, str):
        normalized_id = user_id.strip()
        if not normalized_id:
            return user_id

        try:
            return ObjectId(normalized_id)
        except (InvalidId, TypeError):
            return normalized_id

    return user_id


def _get_site_user_doc(users_collection: Collection, site_user_id: Any) -> Optional[dict[str, Any]]:
    return users_collection.find_one({"_id": _resolve_site_user_id(site_user_id), "is_active": True})


def _build_legacy_region_accounts(legacy_user: User) -> dict[str, dict[str, Any]]:
    accounts: dict[str, dict[str, Any]] = {}

    if legacy_user.psn_email or legacy_user.psn_password_hash:
        accounts["UA"] = {
            "psn_email": legacy_user.psn_email,
            "psn_password_hash": legacy_user.psn_password_hash,
            "psn_password_salt": legacy_user.psn_password_salt,
            "updated_at": legacy_user.updated_at,
        }

    for account in legacy_user.get_all_psn_accounts():
        region = (account.region or "").strip().upper()
        if not region:
            continue

        accounts[region] = {
            "psn_email": account.psn_email,
            "psn_password_hash": account.psn_password_hash,
            "psn_password_salt": account.psn_password_salt,
            "backup_code_hash": account.twofa_backup_code,
            "backup_code_salt": account.twofa_backup_salt,
            "updated_at": account.updated_at,
        }

    return accounts


def _get_or_create_legacy_user(db: Session, *, telegram_id: int, site_user_doc: dict[str, Any]) -> User:
    legacy_user = UserCRUD.get_by_telegram_id(db, telegram_id)
    if legacy_user:
        return legacy_user

    legacy_user = User(
        telegram_id=telegram_id,
        username=site_user_doc.get("username"),
        first_name=site_user_doc.get("first_name"),
        last_name=site_user_doc.get("last_name"),
        preferred_region=site_user_doc.get("preferred_region") or "UA",
        show_ukraine_prices=bool(site_user_doc.get("show_ukraine_prices", False)),
        show_turkey_prices=bool(site_user_doc.get("show_turkey_prices", True)),
        show_india_prices=bool(site_user_doc.get("show_india_prices", False)),
        payment_email=site_user_doc.get("payment_email"),
        psn_email=site_user_doc.get("psn_email"),
        is_active=True,
    )
    db.add(legacy_user)
    db.flush()
    return legacy_user


def sync_site_user_from_telegram(
    *,
    db: Session,
    users_collection: Collection,
    site_user_id: Any,
    telegram_id: Optional[int],
) -> Optional[dict[str, Any]]:
    if telegram_id is None:
        return _get_site_user_doc(users_collection, site_user_id)

    site_user_doc = _get_site_user_doc(users_collection, site_user_id)
    if not site_user_doc:
        return None

    legacy_user = UserCRUD.get_by_telegram_id(db, telegram_id)
    if not legacy_user:
        return site_user_doc

    update_fields: dict[str, Any] = {
        "username": legacy_user.username or site_user_doc.get("username"),
        "first_name": legacy_user.first_name or site_user_doc.get("first_name"),
        "last_name": legacy_user.last_name or site_user_doc.get("last_name"),
        "preferred_region": legacy_user.preferred_region or site_user_doc.get("preferred_region") or "UA",
        "show_ukraine_prices": bool(legacy_user.show_ukraine_prices),
        "show_turkey_prices": bool(legacy_user.show_turkey_prices),
        "show_india_prices": bool(legacy_user.show_india_prices),
        "payment_email": legacy_user.payment_email or site_user_doc.get("payment_email"),
    }

    merged_accounts = dict(site_user_doc.get("psn_accounts") or {})
    accounts_changed = False
    for region, legacy_account in _build_legacy_region_accounts(legacy_user).items():
        current_account = dict(merged_accounts.get(region) or {})

        for key in ("psn_email", "psn_password_hash", "psn_password_salt", "backup_code_hash", "backup_code_salt", "updated_at"):
            value = legacy_account.get(key)
            if value and current_account.get(key) != value:
                current_account[key] = value
                accounts_changed = True

        if current_account:
            merged_accounts[region] = current_account

    if accounts_changed:
        update_fields["psn_accounts"] = merged_accounts

    if merged_accounts.get("UA", {}).get("psn_email"):
        update_fields["psn_email"] = merged_accounts["UA"]["psn_email"]

    if any(site_user_doc.get(key) != value for key, value in update_fields.items()):
        update_fields["updated_at"] = _utcnow()
        users_collection.update_one({"_id": site_user_doc["_id"]}, {"$set": update_fields})
        return _get_site_user_doc(users_collection, site_user_doc["_id"])

    return site_user_doc


def sync_telegram_user_from_site(
    *,
    db: Session,
    users_collection: Collection,
    site_user_id: Any,
) -> Optional[User]:
    site_user_doc = _get_site_user_doc(users_collection, site_user_id)
    if not site_user_doc:
        return None

    telegram_id = site_user_doc.get("telegram_id")
    if telegram_id is None:
        return None

    legacy_user = _get_or_create_legacy_user(db, telegram_id=telegram_id, site_user_doc=site_user_doc)
    legacy_user.username = site_user_doc.get("username") or legacy_user.username
    legacy_user.first_name = site_user_doc.get("first_name") or legacy_user.first_name
    legacy_user.last_name = site_user_doc.get("last_name") or legacy_user.last_name
    legacy_user.preferred_region = site_user_doc.get("preferred_region") or legacy_user.preferred_region or "UA"
    legacy_user.show_ukraine_prices = bool(site_user_doc.get("show_ukraine_prices", legacy_user.show_ukraine_prices))
    legacy_user.show_turkey_prices = bool(site_user_doc.get("show_turkey_prices", legacy_user.show_turkey_prices))
    legacy_user.show_india_prices = bool(site_user_doc.get("show_india_prices", legacy_user.show_india_prices))
    legacy_user.payment_email = site_user_doc.get("payment_email")

    site_accounts = dict(site_user_doc.get("psn_accounts") or {})
    ua_account = dict(site_accounts.get("UA") or {})
    ua_email = ua_account.get("psn_email") or site_user_doc.get("psn_email")
    if ua_email:
        legacy_user.psn_email = ua_email
    if ua_account.get("psn_password_hash") and ua_account.get("psn_password_salt"):
        legacy_user.psn_password_hash = ua_account["psn_password_hash"]
        legacy_user.psn_password_salt = ua_account["psn_password_salt"]

    for region in ("UA", "TR"):
        site_account = dict(site_accounts.get(region) or {})
        if not any(site_account.get(key) for key in ("psn_email", "psn_password_hash", "backup_code_hash")):
            continue

        legacy_account = legacy_user.get_psn_account_for_region(region)
        if legacy_account is None:
            legacy_account = PSNAccount(user_id=legacy_user.id, region=region, is_active=1)
            db.add(legacy_account)

        if site_account.get("psn_email"):
            legacy_account.psn_email = site_account["psn_email"]
        if site_account.get("psn_password_hash") and site_account.get("psn_password_salt"):
            legacy_account.psn_password_hash = site_account["psn_password_hash"]
            legacy_account.psn_password_salt = site_account["psn_password_salt"]
        if site_account.get("backup_code_hash") and site_account.get("backup_code_salt"):
            legacy_account.twofa_backup_code = site_account["backup_code_hash"]
            legacy_account.twofa_backup_salt = site_account["backup_code_salt"]
        legacy_account.is_active = 1
        legacy_account.updated_at = site_account.get("updated_at") or _utcnow()

    legacy_user.updated_at = _utcnow()
    db.commit()
    db.refresh(legacy_user)
    return legacy_user
