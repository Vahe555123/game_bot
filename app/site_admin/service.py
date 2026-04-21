from __future__ import annotations

import os
import asyncio
import logging
import pickle
import re
import threading
from uuid import uuid4
from contextlib import contextmanager
from typing import Any, Optional

from sqlalchemy import case, distinct, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.exceptions import AuthServiceError
from app.auth.schemas import SiteUserPublic
from app.auth.security import hash_password
from app.auth.service import (
    SITE_ROLE_ADMIN,
    build_public_user,
    is_admin_user_doc,
    is_env_admin_telegram_id,
    omit_none_fields,
    resolve_site_user_role,
    resolve_user_identifier,
    _map_integrity_error,
    utcnow,
)
from app.models import User, UserFavoriteProduct
from app.models.site_auth import SiteAuthCode, SiteAuthSession, SiteContent
from app.models.product import Product
from app.models.purchase_order import SitePurchaseOrder
from app.database.connection import SessionLocal
from app.site_orders.service import build_status_label, serialize_purchase_order
from config.settings import settings

from .schemas import (
    AdminDashboardResponse,
    AdminHelpContentResponse,
    AdminHelpContentUpdateRequest,
    AdminProductCreateRequest,
    AdminProductDetailsResponse,
    AdminProductFavoriteRecord,
    AdminProductListResponse,
    AdminProductManualParseRequest,
    AdminProductManualParseStartResponse,
    AdminProductManualParseStatusResponse,
    AdminProductManualParseResponse,
    AdminProductRecord,
    AdminProductSummary,
    AdminProductUpdateRequest,
    AdminPurchaseFulfillRequest,
    AdminPurchaseListResponse,
    AdminPurchaseRecord,
    AdminPurchaseSummary,
    AdminPurchaseUpdateRequest,
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserRecord,
    AdminUserSummary,
)

HELP_CONTENT_DOCUMENT_ID = "help_page"
logger = logging.getLogger(__name__)
_manual_product_parse_lock = asyncio.Lock()
_manual_product_parse_tasks: dict[str, dict[str, Any]] = {}
_manual_product_parse_tasks_lock = asyncio.Lock()


def build_default_help_content(*, updated_at: Any = None) -> dict[str, Any]:
    return {
        "eyebrow": "Помощь",
        "title": "Помощь по покупкам и доступу к заказам",
        "subtitle": (
            "Здесь собраны основные ответы по оплате, истории покупок и связи с менеджером. "
            "Если ситуация нестандартная, откройте поддержку и напишите нам напрямую."
        ),
        "support_title": "Нужна живая помощь?",
        "support_description": (
            "Менеджер поможет с выбором региона, подпиской, ошибкой после оплаты или доступом к заказу."
        ),
        "support_button_label": "Написать менеджеру",
        "support_button_url": settings.MANAGER_TELEGRAM_URL or None,
        "social_links": [
            {"label": "Telegram", "url": settings.MANAGER_TELEGRAM_URL}
        ] if settings.MANAGER_TELEGRAM_URL else [],
        "purchases_title": "Где посмотреть покупки",
        "purchases_description": (
            "История заказов и переписка по ним доступны на oplata.info. "
            "Используйте тот же email, который указан как email для покупок."
        ),
        "purchases_button_label": "Открыть oplata.info",
        "purchases_button_url": "https://oplata.info",
        "sections": [
            {
                "title": "Как оформить заказ",
                "body": (
                    "Выберите товар, проверьте регион и завершите оплату. "
                    "После оплаты все дальнейшие уведомления и покупки будут привязаны к email для покупок."
                ),
            },
            {
                "title": "Как найти уже оплаченный заказ",
                "body": (
                    "Если страница после оплаты закрылась, откройте oplata.info и войдите по email для покупок. "
                    "Там можно найти историю заказов и перейти к нужной покупке."
                ),
            },
            {
                "title": "Когда писать в поддержку",
                "body": (
                    "Если не пришёл код, не открывается доступ или нужен совет по Турции, Индии, Украине, Польше "
                    "или подпискам, сразу напишите менеджеру и приложите номер заказа."
                ),
            },
        ],
        "faq_items": [
            {
                "question": "Где посмотреть мои покупки?",
                "answer": (
                    "Откройте раздел «Мои покупки» или перейдите на oplata.info. "
                    "Используйте email для покупок, чтобы увидеть историю заказов."
                ),
            },
            {
                "question": "Что делать, если после оплаты появилась ошибка?",
                "answer": (
                    "Сначала проверьте почту и папку спам, затем зайдите на oplata.info по email для покупок. "
                    "Если заказ всё ещё недоступен, свяжитесь с менеджером."
                ),
            },
            {
                "question": "Какой email использовать для заказов?",
                "answer": (
                    "Указывайте рабочий email для покупок. К нему привязываются все новые покупки, уведомления и "
                    "возможность позже найти заказ."
                ),
            },
            {
                "question": "Можно ли уточнить регион перед оплатой?",
                "answer": (
                    "Да. Если не уверены, какой регион или тип подписки выбрать, сначала напишите менеджеру "
                    "и получите рекомендацию до оплаты."
                ),
            },
        ],
        "updated_at": updated_at,
    }


def build_admin_user_record(
    user_doc: dict[str, Any],
    *,
    purchase_count: int = 0,
    total_spent_rub: float = 0.0,
) -> AdminUserRecord:
    public_user = build_public_user(user_doc)
    payload = public_user.model_dump()
    telegram_id = user_doc.get("telegram_id") if isinstance(user_doc, dict) else getattr(user_doc, "telegram_id", None)
    payload["is_env_admin"] = is_env_admin_telegram_id(telegram_id)
    payload["purchase_count"] = int(purchase_count)
    payload["total_spent_rub"] = float(total_spent_rub or 0.0)
    return AdminUserRecord(**payload)


def _coerce_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    return str(value).strip() or None


def build_admin_product_record(product: Product, *, favorites_count: int = 0) -> AdminProductRecord:
    return AdminProductRecord(
        id=product.id,
        region=(product.region or "").upper(),
        display_name=_coerce_optional_text(product.name or product.get_display_name()) or product.id,
        favorites_count=int(favorites_count or 0),
        name=_coerce_optional_text(product.name),
        main_name=_coerce_optional_text(product.main_name),
        category=_coerce_optional_text(product.category),
        type=_coerce_optional_text(product.type),
        image=_coerce_optional_text(product.image),
        search_names=_coerce_optional_text(product.search_names),
        platforms=_coerce_optional_text(product.platforms),
        publisher=_coerce_optional_text(product.publisher),
        localization=_coerce_optional_text(product.localization),
        rating=product.rating,
        edition=_coerce_optional_text(product.edition),
        price=product.price,
        old_price=product.old_price,
        ps_price=product.ps_price,
        ea_price=product.ea_price,
        price_uah=product.price_uah,
        old_price_uah=product.old_price_uah,
        price_try=product.price_try,
        old_price_try=product.old_price_try,
        price_inr=product.price_inr,
        old_price_inr=product.old_price_inr,
        ps_plus_price_uah=product.ps_plus_price_uah,
        ps_plus_price_try=product.ps_plus_price_try,
        ps_plus_price_inr=product.ps_plus_price_inr,
        plus_types=_coerce_optional_text(product.plus_types),
        ps_plus=bool(product.ps_plus),
        ea_access=_coerce_optional_text(product.ea_access),
        ps_plus_collection=_coerce_optional_text(product.ps_plus_collection),
        discount=product.discount,
        discount_end=_coerce_optional_text(product.discount_end),
        tags=_coerce_optional_text(product.tags),
        description=_coerce_optional_text(product.description),
        compound=_coerce_optional_text(product.compound),
        info=_coerce_optional_text(product.info),
        players_min=product.players_min,
        players_max=product.players_max,
        players_online=bool(product.players_online),
        has_discount=product.has_discount,
        has_ps_plus=product.has_ps_plus,
        has_ea_access=product.has_ea_access,
    )


def build_admin_product_favorite_record(
    favorite: UserFavoriteProduct,
    user: Optional[User],
) -> AdminProductFavoriteRecord:
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    full_name = " ".join(part for part in [first_name, last_name] if part).strip() or getattr(user, "username", None)

    return AdminProductFavoriteRecord(
        id=favorite.id,
        user_id=favorite.user_id,
        telegram_id=getattr(user, "telegram_id", None),
        username=getattr(user, "username", None),
        first_name=first_name,
        last_name=last_name,
        full_name=full_name or None,
        preferred_region=getattr(user, "preferred_region", None),
        payment_email=getattr(user, "payment_email", None),
        platform=getattr(user, "platform", None),
        psn_email=getattr(user, "psn_email", None),
        region=favorite.region,
        is_active=bool(getattr(user, "is_active", False)),
        favorited_at=favorite.created_at,
    )


def build_admin_purchase_record(order: SitePurchaseOrder) -> AdminPurchaseRecord:
    order_payload = serialize_purchase_order(order).model_dump()
    order_payload["site_user_id"] = order.site_user_id
    order_payload["user_email"] = order.user_email
    order_payload["user_display_name"] = order.user_display_name
    return AdminPurchaseRecord(**order_payload)


class SiteAdminService:
    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        now_provider=utcnow,
    ) -> None:
        self.session_factory = session_factory
        self.now_provider = now_provider

    @contextmanager
    def _session(self):
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

    def get_dashboard(self, db: Session) -> AdminDashboardResponse:
        users_summary = self._build_user_summary(db)
        products_summary = self._build_product_summary(db)
        purchases_summary = self._build_purchase_summary(db)

        recent_user_docs = (
            db.query(User)
            .order_by(User.updated_at.desc(), User.id.desc())
            .limit(8)
            .all()
        )
        recent_user_ids = [str(doc.id) for doc in recent_user_docs]
        purchase_stats = self._get_purchase_stats_for_users(db, recent_user_ids)
        recent_users = [
            build_admin_user_record(
                doc,
                purchase_count=purchase_stats.get(str(doc.id), {}).get("purchase_count", 0),
                total_spent_rub=purchase_stats.get(str(doc.id), {}).get("total_spent_rub", 0.0),
            )
            for doc in recent_user_docs
        ]

        recent_orders = [
            build_admin_purchase_record(order)
            for order in (
                db.query(SitePurchaseOrder)
                .order_by(SitePurchaseOrder.created_at.desc(), SitePurchaseOrder.id.desc())
                .limit(8)
                .all()
            )
        ]

        return AdminDashboardResponse(
            users=users_summary,
            products=products_summary,
            purchases=purchases_summary,
            recent_users=recent_users,
            recent_orders=recent_orders,
        )

    def get_help_content(self) -> AdminHelpContentResponse:
        with self._session() as db:
            content_doc = (
                db.query(SiteContent)
                .filter(SiteContent.content_key == HELP_CONTENT_DOCUMENT_ID)
                .first()
            )
            return self._serialize_help_content(content_doc)

    def update_help_content(self, payload: AdminHelpContentUpdateRequest) -> AdminHelpContentResponse:
        current_time = self.now_provider()
        with self._session() as db:
            content_doc = (
                db.query(SiteContent)
                .filter(SiteContent.content_key == HELP_CONTENT_DOCUMENT_ID)
                .first()
            )
            if not content_doc:
                content_doc = SiteContent(content_key=HELP_CONTENT_DOCUMENT_ID, payload_json="{}")
                db.add(content_doc)

            payload_data = payload.model_dump()
            payload_data["updated_at"] = current_time.isoformat()
            content_doc.set_payload(payload_data)
            content_doc.updated_at = current_time
            content_doc.created_at = content_doc.created_at or current_time
            db.add(content_doc)
            db.commit()
            db.refresh(content_doc)
            return self._serialize_help_content(content_doc)

    def list_users(
        self,
        db: Session,
        *,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> AdminUserListResponse:
        query = db.query(User)

        if role:
            normalized_role = resolve_site_user_role(role)
            if normalized_role == SITE_ROLE_ADMIN and settings.ADMIN_TELEGRAM_IDS:
                query = query.filter(
                    or_(
                        User.role == SITE_ROLE_ADMIN,
                        User.telegram_id.in_(settings.ADMIN_TELEGRAM_IDS),
                    )
                )
            elif normalized_role == SITE_ROLE_CLIENT and settings.ADMIN_TELEGRAM_IDS:
                query = query.filter(
                    or_(User.role == SITE_ROLE_CLIENT, User.role.is_(None)),
                    ~User.telegram_id.in_(settings.ADMIN_TELEGRAM_IDS),
                )
            else:
                query = query.filter(User.role == normalized_role)

        if is_active is not None:
            query = query.filter(User.is_active.is_(bool(is_active)))

        if search:
            pattern = f"%{search.strip()}%"
            search_filters = [
                User.email.ilike(pattern),
                User.email_normalized.ilike(pattern),
                User.username.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            ]
            if search.strip().isdigit():
                search_filters.append(User.telegram_id == int(search.strip()))
            query = query.filter(or_(*search_filters))

        total = query.count()
        skip = max(page - 1, 0) * limit
        user_docs = (
            query.order_by(User.created_at.desc(), User.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        purchase_stats = self._get_purchase_stats_for_users(
            db,
            [str(doc.id) for doc in user_docs],
        )

        return AdminUserListResponse(
            users=[
                build_admin_user_record(
                    doc,
                    purchase_count=purchase_stats.get(str(doc.id), {}).get("purchase_count", 0),
                    total_spent_rub=purchase_stats.get(str(doc.id), {}).get("total_spent_rub", 0.0),
                )
                for doc in user_docs
            ],
            total=total,
            page=page,
            limit=limit,
        )

    def create_user(self, payload: AdminUserCreateRequest) -> AdminUserRecord:
        current_time = self.now_provider()
        with self._session() as db:
            user = User(
                email=payload.email,
                email_normalized=payload.email,
                email_verified=bool(payload.email and payload.email_verified),
                username=payload.username,
                first_name=payload.first_name,
                last_name=payload.last_name,
                telegram_id=payload.telegram_id,
                preferred_region=payload.preferred_region,
                show_ukraine_prices=payload.preferred_region == "UA",
                show_turkey_prices=payload.preferred_region == "TR",
                show_india_prices=payload.preferred_region == "IN",
                payment_email=payload.payment_email,
                platform=payload.platform,
                psn_email=payload.psn_email,
                role=resolve_site_user_role(payload.role, telegram_id=payload.telegram_id),
                is_active=bool(payload.is_active),
                created_at=current_time,
                updated_at=current_time,
                last_login_at=None,
                last_registration_at=current_time,
                registration_user_agent="admin-panel",
                registration_ip_address=None,
            )
            if payload.password:
                user.set_password(payload.password)
            user.auth_providers = []
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
            except IntegrityError as error:
                db.rollback()
                raise _map_integrity_error(error) from error
            return build_admin_user_record(user)

    def update_user(
        self,
        user_id: str,
        payload: AdminUserUpdateRequest,
        *,
        current_admin: SiteUserPublic,
    ) -> AdminUserRecord:
        resolved_user_id = resolve_user_identifier(user_id)
        if not isinstance(resolved_user_id, int):
            raise AuthServiceError(404, "Пользователь не найден.")

        with self._session() as db:
            existing_user = db.query(User).filter(User.id == resolved_user_id).first()
            if not existing_user:
                raise AuthServiceError(404, "Пользователь не найден.")

            is_self = str(existing_user.id) == current_admin.id
            is_env_admin = is_env_admin_telegram_id(existing_user.telegram_id)
            next_telegram_id = payload.telegram_id if payload.telegram_id is not None else existing_user.telegram_id
            next_role = (
                resolve_site_user_role(payload.role, telegram_id=next_telegram_id)
                if payload.role is not None or payload.telegram_id is not None
                else resolve_site_user_role(existing_user.role, telegram_id=next_telegram_id)
            )

            if is_env_admin and next_role != SITE_ROLE_ADMIN:
                raise AuthServiceError(400, "Администратор из .env должен оставаться администратором.")
            if is_self and next_role != SITE_ROLE_ADMIN:
                raise AuthServiceError(400, "Нельзя снять роль администратора у самого себя.")
            if is_self and payload.is_active is False:
                raise AuthServiceError(400, "Нельзя деактивировать собственный аккаунт администратора.")

            existing_user.role = next_role
            if payload.email is not None:
                email_changed = payload.email != existing_user.email_normalized
                existing_user.email = payload.email
                existing_user.email_normalized = payload.email
                if payload.email_verified is not None:
                    existing_user.email_verified = payload.email_verified
                elif email_changed:
                    existing_user.email_verified = False
            elif payload.email_verified is not None:
                existing_user.email_verified = payload.email_verified

            if payload.password:
                existing_user.set_password(payload.password)
            if payload.username is not None:
                existing_user.username = payload.username
            if payload.first_name is not None:
                existing_user.first_name = payload.first_name
            if payload.last_name is not None:
                existing_user.last_name = payload.last_name
            if payload.telegram_id is not None:
                existing_user.telegram_id = payload.telegram_id
            if payload.payment_email is not None:
                existing_user.payment_email = payload.payment_email
            if payload.platform is not None:
                existing_user.platform = payload.platform
            if payload.psn_email is not None:
                existing_user.psn_email = payload.psn_email
            if payload.is_active is not None:
                existing_user.is_active = payload.is_active

            if payload.preferred_region is not None:
                existing_user.preferred_region = payload.preferred_region
                existing_user.show_ukraine_prices = payload.preferred_region == "UA"
                existing_user.show_turkey_prices = payload.preferred_region == "TR"
                existing_user.show_india_prices = payload.preferred_region == "IN"

            existing_user.updated_at = self.now_provider()
            db.add(existing_user)
            try:
                db.commit()
                db.refresh(existing_user)
            except IntegrityError as error:
                db.rollback()
                raise _map_integrity_error(error) from error

            return build_admin_user_record(existing_user)

    def delete_user(self, user_id: str, *, current_admin: SiteUserPublic) -> None:
        resolved_user_id = resolve_user_identifier(user_id)
        if not isinstance(resolved_user_id, int):
            raise AuthServiceError(404, "Пользователь не найден.")

        with self._session() as db:
            existing_user = db.query(User).filter(User.id == resolved_user_id).first()
            if not existing_user:
                raise AuthServiceError(404, "Пользователь не найден.")

            if str(existing_user.id) == current_admin.id:
                raise AuthServiceError(400, "Нельзя удалить собственный аккаунт администратора.")
            if is_env_admin_telegram_id(existing_user.telegram_id):
                raise AuthServiceError(400, "Нельзя удалить администратора из .env.")

            db.query(SiteAuthSession).filter(SiteAuthSession.user_id == existing_user.id).delete(synchronize_session=False)
            db.query(SiteAuthCode).filter(SiteAuthCode.user_id == existing_user.id).delete(synchronize_session=False)
            db.delete(existing_user)
            db.commit()

    def list_products(
        self,
        db: Session,
        *,
        page: int = 1,
        limit: int = 24,
        search: Optional[str] = None,
        region: Optional[str] = None,
        category: Optional[str] = None,
        sort: Optional[str] = None,
        missing_region: Optional[str] = None,
    ) -> AdminProductListResponse:
        favorites_subquery = (
            db.query(
                UserFavoriteProduct.product_id.label("product_id"),
                func.count(UserFavoriteProduct.id).label("favorites_count"),
            )
            .group_by(UserFavoriteProduct.product_id)
            .subquery()
        )

        query = db.query(Product, func.coalesce(favorites_subquery.c.favorites_count, 0).label("favorites_count")).outerjoin(
            favorites_subquery,
            favorites_subquery.c.product_id == Product.id,
        )
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Product.id.ilike(pattern),
                    Product.name.ilike(pattern),
                    Product.main_name.ilike(pattern),
                    Product.search_names.ilike(pattern),
                    Product.publisher.ilike(pattern),
                )
            )
        if region:
            query = query.filter(Product.region == region.strip().upper())
        if category:
            query = query.filter(Product.category == category.strip())

        # Фильтр по отсутствующим регионам. Значения:
        #   "any" / "incomplete"  — у товара < 3 региональных строк;
        #   "TR" / "UA" / "IN"    — конкретный регион отсутствует у товара.
        normalized_missing = (missing_region or "").strip().upper()
        if normalized_missing:
            regions_subquery = (
                db.query(
                    Product.id.label("product_id"),
                    func.count(func.distinct(Product.region)).label("regions_count"),
                    func.group_concat(Product.region).label("regions_list"),
                )
                .group_by(Product.id)
                .subquery()
            )
            query = query.outerjoin(regions_subquery, regions_subquery.c.product_id == Product.id)
            if normalized_missing in ("ANY", "INCOMPLETE"):
                query = query.filter(regions_subquery.c.regions_count < 3)
            elif normalized_missing in ("TR", "UA", "IN"):
                query = query.filter(
                    ~regions_subquery.c.regions_list.like(f"%{normalized_missing}%")
                )

        total = query.count()
        normalized_sort = (sort or "popular").strip().lower()
        if normalized_sort == "alphabet":
            query = query.order_by(Product.main_name.asc(), Product.name.asc(), Product.region.asc())
        elif normalized_sort in {"added", "added_desc", "created", "created_desc", "new", "newest", "db_added"}:
            null_added_last = case((Product.created_at.is_(None), 1), else_=0)
            query = query.order_by(
                null_added_last.asc(),
                Product.created_at.desc(),
                Product.main_name.asc(),
                Product.name.asc(),
                Product.region.asc(),
            )
        elif normalized_sort in {"release", "release_desc", "release_date", "released", "new_releases"}:
            null_release_last = case((Product.release_date.is_(None), 1), else_=0)
            query = query.order_by(
                null_release_last.asc(),
                Product.release_date.desc(),
                Product.main_name.asc(),
                Product.name.asc(),
                Product.region.asc(),
            )
        else:
            query = query.order_by(
                func.coalesce(favorites_subquery.c.favorites_count, 0).desc(),
                Product.main_name.asc(),
                Product.name.asc(),
                Product.region.asc(),
            )

        product_rows = (
            query
            .offset(max(page - 1, 0) * limit)
            .limit(limit)
            .all()
        )
        return AdminProductListResponse(
            products=[
                build_admin_product_record(
                    product,
                    favorites_count=int(favorites_count or 0),
                )
                for product, favorites_count in product_rows
            ],
            total=total,
            page=page,
            limit=limit,
        )

    def get_product(self, db: Session, *, product_id: str, region: str) -> AdminProductDetailsResponse:
        product = self._get_product_or_error(db, product_id=product_id, region=region)
        return self._build_product_details(db, product)

    def create_product(self, db: Session, payload: AdminProductCreateRequest) -> AdminProductDetailsResponse:
        existing = (
            db.query(Product)
            .filter(Product.id == payload.id, Product.region == payload.region)
            .first()
        )
        if existing:
            raise AuthServiceError(409, "Товар с таким ID и регионом уже существует.")

        product = Product(id=payload.id, region=payload.region)
        self._apply_product_payload(product, payload)
        db.add(product)
        db.commit()
        db.refresh(product)
        return self._build_product_details(db, product)

    async def manual_parse_product(
        self,
        payload: AdminProductManualParseRequest,
    ) -> AdminProductManualParseStartResponse:
        task_id = uuid4().hex
        async with _manual_product_parse_tasks_lock:
            _manual_product_parse_tasks[task_id] = {
                "status": "pending",
                "message": "Задача поставлена в очередь на ручной парсинг.",
                "result": None,
            }

        async def _run_manual_parse() -> None:
            async with _manual_product_parse_tasks_lock:
                task = _manual_product_parse_tasks.get(task_id)
                if task is not None:
                    task["status"] = "running"
                    task["message"] = "Идёт ручной парсинг товара, это может занять несколько минут."

            async with _manual_product_parse_lock:
                try:
                    from parser import run_manual_product_parse

                    result = await run_manual_product_parse(
                        ua_url=payload.ua_url,
                        tr_url=payload.tr_url,
                        in_url=payload.in_url,
                        save_to_db=payload.save_to_db,
                    )
                    parsed_result = AdminProductManualParseResponse(**result)

                    if payload.save_to_db and settings.PRODUCTS_USE_CARDS_TABLE:
                        from app.database.connection import engine
                        from app.database.product_card_rebuilder import rebuild_product_cards

                        with engine.begin() as connection:
                            rebuild_product_cards(connection)

                    async with _manual_product_parse_tasks_lock:
                        task = _manual_product_parse_tasks.get(task_id)
                        if task is not None:
                            task["status"] = "completed"
                            task["message"] = "Ручной парсинг завершён."
                            task["result"] = parsed_result
                except ValueError as error:
                    async with _manual_product_parse_tasks_lock:
                        task = _manual_product_parse_tasks.get(task_id)
                        if task is not None:
                            task["status"] = "failed"
                            task["message"] = str(error)
                except Exception as error:
                    logger.exception("Manual product parse failed")
                    async with _manual_product_parse_tasks_lock:
                        task = _manual_product_parse_tasks.get(task_id)
                        if task is not None:
                            task["status"] = "failed"
                            task["message"] = f"Ручной парсинг не удался: {type(error).__name__}: {error}"

        asyncio.create_task(_run_manual_parse())
        return AdminProductManualParseStartResponse(
            task_id=task_id,
            status="pending",
            message="Ручной парсинг запущен в фоне.",
        )

    async def get_manual_parse_product_status(self, task_id: str) -> AdminProductManualParseStatusResponse:
        async with _manual_product_parse_tasks_lock:
            task = _manual_product_parse_tasks.get(task_id)

        if task is None:
            raise AuthServiceError(404, "Задача ручного парсинга не найдена.")

        return AdminProductManualParseStatusResponse(
            task_id=task_id,
            status=str(task.get("status") or "pending"),
            message=str(task.get("message") or ""),
            result=task.get("result"),
        )

    def update_product(
        self,
        db: Session,
        *,
        product_id: str,
        region: str,
        payload: AdminProductUpdateRequest,
    ) -> AdminProductDetailsResponse:
        product = self._get_product_or_error(db, product_id=product_id, region=region)
        self._apply_product_payload(product, payload)
        db.add(product)
        db.commit()
        db.refresh(product)
        return self._build_product_details(db, product)

    def delete_product(self, db: Session, *, product_id: str, region: str) -> None:
        product = self._get_product_or_error(db, product_id=product_id, region=region)
        db.delete(product)
        db.commit()
        remaining_rows = db.query(func.count(Product.id)).filter(Product.id == product_id).scalar() or 0
        if remaining_rows == 0:
            db.query(UserFavoriteProduct).filter(UserFavoriteProduct.product_id == product_id).delete()
            db.commit()

    def delete_product_group(self, db: Session, *, product_id: str) -> int:
        products = db.query(Product).filter(Product.id == product_id).all()
        if not products:
            raise AuthServiceError(404, "Товар не найден.")

        deleted_count = len(products)
        db.query(UserFavoriteProduct).filter(UserFavoriteProduct.product_id == product_id).delete()
        for product in products:
            db.delete(product)
        db.commit()
        return deleted_count

    def delete_product_favorite(self, db: Session, *, product_id: str, favorite_id: int) -> None:
        favorite = (
            db.query(UserFavoriteProduct)
            .filter(
                UserFavoriteProduct.id == favorite_id,
                UserFavoriteProduct.product_id == product_id,
            )
            .first()
        )
        if not favorite:
            raise AuthServiceError(404, "Запись избранного не найдена.")

        db.delete(favorite)
        db.commit()

    def list_unparsed_urls(
        self,
        db: Session,
        *,
        page: int = 1,
        limit: int = 100,
        mode: str = "missing_any",
        locale: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        """Сравнивает products.pkl с products-таблицей и возвращает URL,
        по которым нет записей в БД (mode='missing_any' — не хватает региона URL'а,
        mode='missing_all' — в БД нет ни одного региона для этого id,
        mode='all' — все URL)."""
        urls = _load_products_pkl_urls()
        db_regions_by_id = _load_db_regions_by_id(db)

        normalized_mode = (mode or "missing_any").strip().lower()
        normalized_locale = (locale or "").strip().lower() or None
        search_term = (search or "").strip().lower() or None

        items: list[dict] = []
        missing_by_locale: dict[str, int] = {}

        for raw_url in urls:
            url = raw_url.strip()
            if not url:
                continue
            parts = url.rstrip("/").split("/")
            if len(parts) < 5:
                continue
            url_locale = parts[3]
            product_id = parts[-1].upper()
            expected_region = _LOCALE_TO_REGION.get(url_locale)
            db_regions = db_regions_by_id.get(product_id, set())

            # Фильтры выборки
            if normalized_locale and url_locale != normalized_locale:
                continue
            if search_term and search_term not in url.lower():
                continue

            if normalized_mode == "missing_all":
                include = len(db_regions) == 0
            elif normalized_mode == "all":
                include = True
            else:  # missing_any
                if expected_region:
                    include = expected_region not in db_regions
                else:
                    include = len(db_regions) == 0

            if not include:
                continue

            missing_by_locale[url_locale] = missing_by_locale.get(url_locale, 0) + 1
            items.append(
                {
                    "url": url,
                    "locale": url_locale,
                    "product_id": product_id,
                    "exists_in_regions": sorted(db_regions),
                    "missing_regions": sorted(
                        r for r in ("UA", "TR", "IN") if r not in db_regions
                    ),
                }
            )

        total = len(items)
        offset = max(page - 1, 0) * limit
        page_items = items[offset : offset + limit]

        return {
            "total_urls_in_pkl": len(urls),
            "parsed_ids": len(db_regions_by_id),
            "unparsed_total": total,
            "missing_by_locale": missing_by_locale,
            "items": page_items,
            "page": page,
            "limit": limit,
        }

    def list_purchases(
        self,
        db: Session,
        *,
        page: int = 1,
        limit: int = 30,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> AdminPurchaseListResponse:
        query = db.query(SitePurchaseOrder)
        if status:
            query = query.filter(SitePurchaseOrder.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    SitePurchaseOrder.order_number.ilike(pattern),
                    SitePurchaseOrder.product_name.ilike(pattern),
                    SitePurchaseOrder.user_email.ilike(pattern),
                    SitePurchaseOrder.payment_email.ilike(pattern),
                )
            )

        total = query.count()
        orders = (
            query.order_by(SitePurchaseOrder.created_at.desc(), SitePurchaseOrder.id.desc())
            .offset(max(page - 1, 0) * limit)
            .limit(limit)
            .all()
        )
        return AdminPurchaseListResponse(
            orders=[build_admin_purchase_record(order) for order in orders],
            total=total,
            page=page,
            limit=limit,
        )

    def get_purchase(self, db: Session, *, order_number: str) -> AdminPurchaseRecord:
        order = self._get_order_or_error(db, order_number=order_number)
        return build_admin_purchase_record(order)

    def update_purchase(
        self,
        db: Session,
        *,
        order_number: str,
        payload: AdminPurchaseUpdateRequest,
    ) -> AdminPurchaseRecord:
        order = self._get_order_or_error(db, order_number=order_number)
        current_time = self.now_provider()

        if payload.status is not None:
            order.status = payload.status
            if payload.status == "payment_review" and not order.payment_submitted_at:
                order.payment_submitted_at = current_time
            if payload.status == "fulfilled" and not order.fulfilled_at:
                order.fulfilled_at = current_time
            if payload.status != "fulfilled":
                order.fulfilled_at = None

        if payload.status_note is not None:
            order.status_note = payload.status_note
        if payload.manager_contact_url is not None:
            order.manager_contact_url = payload.manager_contact_url
        if payload.payment_url is not None:
            order.payment_url = payload.payment_url

        order.updated_at = current_time
        db.add(order)
        db.commit()
        db.refresh(order)
        return build_admin_purchase_record(order)

    def fulfill_purchase(
        self,
        db: Session,
        *,
        order_number: str,
        payload: AdminPurchaseFulfillRequest,
    ) -> AdminPurchaseRecord:
        order = self._get_order_or_error(db, order_number=order_number)
        current_time = self.now_provider()

        order.status = "fulfilled"
        order.delivery_title = payload.delivery_title or "Данные по заказу"
        order.delivery_message = payload.delivery_message
        order.status_note = payload.status_note
        order.payment_submitted_at = order.payment_submitted_at or current_time
        order.fulfilled_at = current_time
        order.updated_at = current_time
        order.set_delivery_items([item.model_dump() for item in payload.delivery_items])

        db.add(order)
        db.commit()
        db.refresh(order)
        return build_admin_purchase_record(order)

    def delete_purchase(self, db: Session, *, order_number: str) -> None:
        order = self._get_order_or_error(db, order_number=order_number)
        db.delete(order)
        db.commit()

    def _serialize_help_content(self, content_doc: Optional[Any]) -> AdminHelpContentResponse:
        if not content_doc:
            return AdminHelpContentResponse(**build_default_help_content())

        payload = build_default_help_content(updated_at=getattr(content_doc, "updated_at", None))
        if hasattr(content_doc, "get_payload"):
            content_payload = content_doc.get_payload()
        elif isinstance(content_doc, dict):
            content_payload = dict(content_doc)
        else:
            content_payload = {}

        for field_name in (
            "eyebrow",
            "title",
            "subtitle",
            "support_title",
            "support_description",
            "support_button_label",
            "support_button_url",
            "purchases_title",
            "purchases_description",
            "purchases_button_label",
            "purchases_button_url",
            "social_links",
            "sections",
            "faq_items",
            "updated_at",
        ):
            if field_name in content_payload:
                payload[field_name] = content_payload[field_name]

        return AdminHelpContentResponse(**payload)

    def _build_user_summary(self, db: Session) -> AdminUserSummary:
        total = db.query(func.count(User.id)).scalar() or 0
        active = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
        verified = db.query(func.count(User.id)).filter(User.email_verified.is_(True)).scalar() or 0

        if settings.ADMIN_TELEGRAM_IDS:
            admins = (
                db.query(func.count(User.id))
                .filter(
                    or_(
                        User.role == SITE_ROLE_ADMIN,
                        User.telegram_id.in_(settings.ADMIN_TELEGRAM_IDS),
                    )
                )
                .scalar()
                or 0
            )
        else:
            admins = db.query(func.count(User.id)).filter(User.role == SITE_ROLE_ADMIN).scalar() or 0

        clients = max(int(total) - int(admins), 0)

        return AdminUserSummary(
            total=int(total),
            active=int(active),
            verified=int(verified),
            admins=int(admins),
            clients=clients,
        )

    def _build_product_summary(self, db: Session) -> AdminProductSummary:
        total_rows = db.query(func.count(Product.id)).scalar() or 0
        unique_products = db.query(func.count(distinct(Product.id))).scalar() or 0
        discounted = db.query(func.count(Product.id)).filter(Product.discount.isnot(None), Product.discount > 0).scalar() or 0
        with_ps_plus = db.query(func.count(Product.id)).filter(Product.ps_plus == 1).scalar() or 0

        regions = {
            region: count
            for region, count in db.query(Product.region, func.count(Product.id)).group_by(Product.region).all()
            if region
        }

        return AdminProductSummary(
            total_rows=int(total_rows),
            unique_products=int(unique_products),
            discounted=int(discounted),
            with_ps_plus=int(with_ps_plus),
            regions=regions,
        )

    def _build_purchase_summary(self, db: Session) -> AdminPurchaseSummary:
        total = db.query(func.count(SitePurchaseOrder.id)).scalar() or 0
        total_revenue_rub = db.query(func.coalesce(func.sum(SitePurchaseOrder.price_rub), 0)).scalar() or 0.0
        fulfilled_revenue_rub = (
            db.query(func.coalesce(func.sum(SitePurchaseOrder.price_rub), 0))
            .filter(SitePurchaseOrder.status == "fulfilled")
            .scalar()
            or 0.0
        )
        statuses = {
            status: count
            for status, count in db.query(
                SitePurchaseOrder.status,
                func.count(SitePurchaseOrder.id),
            ).group_by(SitePurchaseOrder.status).all()
            if status
        }

        return AdminPurchaseSummary(
            total=int(total),
            total_revenue_rub=float(total_revenue_rub),
            fulfilled_revenue_rub=float(fulfilled_revenue_rub),
            statuses=statuses,
        )

    def _get_purchase_stats_for_users(self, db: Session, user_ids: list[str]) -> dict[str, dict[str, float]]:
        if not user_ids:
            return {}

        rows = (
            db.query(
                SitePurchaseOrder.site_user_id,
                func.count(SitePurchaseOrder.id),
                func.coalesce(func.sum(SitePurchaseOrder.price_rub), 0),
            )
            .filter(SitePurchaseOrder.site_user_id.in_(user_ids))
            .group_by(SitePurchaseOrder.site_user_id)
            .all()
        )
        return {
            str(site_user_id): {
                "purchase_count": int(purchase_count),
                "total_spent_rub": float(total_spent_rub or 0.0),
            }
            for site_user_id, purchase_count, total_spent_rub in rows
        }

    def _get_product_favorites_count(self, db: Session, *, product_id: str) -> int:
        return db.query(func.count(UserFavoriteProduct.id)).filter(UserFavoriteProduct.product_id == product_id).scalar() or 0

    def _get_product_favorites(self, db: Session, *, product_id: str) -> list[AdminProductFavoriteRecord]:
        favorite_rows = (
            db.query(UserFavoriteProduct, User)
            .outerjoin(User, User.id == UserFavoriteProduct.user_id)
            .filter(UserFavoriteProduct.product_id == product_id)
            .order_by(UserFavoriteProduct.created_at.desc(), UserFavoriteProduct.id.desc())
            .all()
        )
        return [
            build_admin_product_favorite_record(favorite, user)
            for favorite, user in favorite_rows
        ]

    def _build_product_details(self, db: Session, product: Product) -> AdminProductDetailsResponse:
        favorites_count = self._get_product_favorites_count(db, product_id=product.id)
        favorites = self._get_product_favorites(db, product_id=product.id)
        regional_products = db.query(Product).filter(Product.id == product.id).all()
        region_order = {"TR": 0, "UA": 1, "IN": 2}
        regional_products.sort(key=lambda item: (region_order.get((item.region or "").upper(), 99), item.region or ""))
        regional_records = [
            build_admin_product_record(regional_product, favorites_count=favorites_count)
            for regional_product in regional_products
        ]

        available_regions = [record.region for record in regional_records if record.region]
        missing_regions = [
            region_code
            for region_code in ("TR", "UA", "IN")
            if region_code not in set(available_regions)
        ]
        favorites_by_region: dict[str, int] = {}
        for favorite in favorites:
            region_code = (favorite.region or "").upper() or "UNKNOWN"
            favorites_by_region[region_code] = favorites_by_region.get(region_code, 0) + 1

        payload = build_admin_product_record(product, favorites_count=favorites_count).model_dump()
        payload.update(
            regional_products=regional_records,
            favorites=favorites,
            available_regions=available_regions,
            missing_regions=missing_regions,
            favorites_by_region=favorites_by_region,
            regional_rows_total=len(regional_records),
            favorite_users_total=favorites_count,
        )
        return AdminProductDetailsResponse(**payload)

    def _get_product_or_error(self, db: Session, *, product_id: str, region: str) -> Product:
        product = db.query(Product).filter(Product.id == product_id, Product.region == region.upper()).first()
        if not product:
            raise AuthServiceError(404, "Товар не найден.")
        return product

    def _apply_product_payload(
        self,
        product: Product,
        payload: AdminProductCreateRequest | AdminProductUpdateRequest,
    ) -> None:
        for field_name, value in payload.model_dump(exclude_unset=True).items():
            if field_name in {"id", "region"}:
                continue
            if field_name == "ps_plus" and value is not None:
                setattr(product, field_name, 1 if value else 0)
                continue
            if field_name == "players_online" and value is not None:
                setattr(product, field_name, 1 if value else 0)
                continue
            setattr(product, field_name, value)

    def _get_order_or_error(self, db: Session, *, order_number: str) -> SitePurchaseOrder:
        order = db.query(SitePurchaseOrder).filter(SitePurchaseOrder.order_number == order_number).first()
        if not order:
            raise AuthServiceError(404, "Заказ не найден.")
        return order


_site_admin_service: Optional[SiteAdminService] = None


def get_site_admin_service() -> SiteAdminService:
    global _site_admin_service
    if _site_admin_service is None:
        _site_admin_service = SiteAdminService()
    return _site_admin_service


# ==========================================================
# products.pkl <-> БД diff (для админского "Не спарсенные URL")
# ==========================================================

_LOCALE_TO_REGION = {
    "ru-ua": "UA",
    "en-tr": "TR",
    "en-in": "IN",
}

_PRODUCTS_PKL_CACHE: dict[str, Any] = {"mtime": None, "urls": None}
_DB_REGIONS_CACHE: dict[str, Any] = {"signature": None, "regions_by_id": None}
_UNPARSED_LOCK = threading.Lock()


def _products_pkl_path() -> str:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(project_root, "products.pkl")


def _load_products_pkl_urls() -> list[str]:
    path = _products_pkl_path()
    if not os.path.exists(path):
        return []
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []

    with _UNPARSED_LOCK:
        if _PRODUCTS_PKL_CACHE["mtime"] == mtime and _PRODUCTS_PKL_CACHE["urls"] is not None:
            return _PRODUCTS_PKL_CACHE["urls"]

        try:
            with open(path, "rb") as handle:
                data = pickle.load(handle)
        except Exception:
            return []

        urls: list[str] = []
        if isinstance(data, list):
            urls = [str(x) for x in data if x]
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, str):
                    urls.append(value)

        _PRODUCTS_PKL_CACHE["mtime"] = mtime
        _PRODUCTS_PKL_CACHE["urls"] = urls
        return urls


def _load_db_regions_by_id(db: Session) -> dict[str, set[str]]:
    """Возвращает {product_id: {"UA","TR","IN"} подмножество} по текущему состоянию БД.
    Кэшируется по суммарному числу строк — если счёт не менялся, возвращается кэш."""
    total_rows = db.query(func.count(Product.id)).scalar() or 0
    signature = total_rows

    with _UNPARSED_LOCK:
        if (
            _DB_REGIONS_CACHE["signature"] == signature
            and _DB_REGIONS_CACHE["regions_by_id"] is not None
        ):
            return _DB_REGIONS_CACHE["regions_by_id"]

        rows = db.query(Product.id, Product.region).all()
        regions_by_id: dict[str, set[str]] = {}
        for product_id, region in rows:
            if not product_id:
                continue
            pid = str(product_id).upper()
            reg = (region or "").upper()
            bucket = regions_by_id.setdefault(pid, set())
            if reg:
                bucket.add(reg)

        _DB_REGIONS_CACHE["signature"] = signature
        _DB_REGIONS_CACHE["regions_by_id"] = regions_by_id
        return regions_by_id

