from __future__ import annotations

import re
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError
from sqlalchemy import distinct, func, or_
from sqlalchemy.orm import Session

from app.auth.exceptions import AuthServiceError
from app.auth.mongo import (
    get_auth_codes_collection,
    get_auth_sessions_collection,
    get_auth_users_collection,
)
from app.auth.schemas import SiteUserPublic
from app.auth.security import hash_password
from app.auth.service import (
    SITE_ROLE_ADMIN,
    build_public_user,
    is_admin_user_doc,
    is_env_admin_telegram_id,
    resolve_site_user_role,
    resolve_user_identifier,
    utcnow,
)
from app.models.product import Product
from app.models.purchase_order import SitePurchaseOrder
from app.site_orders.service import build_status_label, serialize_purchase_order
from config.settings import settings

from .schemas import (
    AdminDashboardResponse,
    AdminProductCreateRequest,
    AdminProductListResponse,
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


def _safe_object_id(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return value

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return value
        try:
            return ObjectId(cleaned)
        except (InvalidId, TypeError):
            return value

    return value


def _map_duplicate_key_error(error: DuplicateKeyError) -> AuthServiceError:
    error_text = str(error)
    if "telegram_id" in error_text:
        return AuthServiceError(409, "Этот Telegram ID уже привязан к другому аккаунту.")
    if "google_id" in error_text:
        return AuthServiceError(409, "Этот Google аккаунт уже привязан к другому профилю.")
    if "vk_id" in error_text:
        return AuthServiceError(409, "Этот VK аккаунт уже привязан к другому профилю.")
    if "email_normalized" in error_text or "email" in error_text:
        return AuthServiceError(409, "Пользователь с таким email уже существует.")
    return AuthServiceError(409, "Пользователь с такими данными уже существует.")


def build_admin_user_record(
    user_doc: dict[str, Any],
    *,
    purchase_count: int = 0,
    total_spent_rub: float = 0.0,
) -> AdminUserRecord:
    public_user = build_public_user(user_doc)
    payload = public_user.model_dump()
    payload["is_env_admin"] = is_env_admin_telegram_id(user_doc.get("telegram_id"))
    payload["purchase_count"] = int(purchase_count)
    payload["total_spent_rub"] = float(total_spent_rub or 0.0)
    return AdminUserRecord(**payload)


def build_admin_product_record(product: Product) -> AdminProductRecord:
    return AdminProductRecord(
        id=product.id,
        region=(product.region or "").upper(),
        display_name=product.name or product.get_display_name(),
        name=product.name,
        main_name=product.main_name,
        category=product.category,
        type=product.type,
        image=product.image,
        search_names=product.search_names,
        platforms=product.platforms,
        publisher=product.publisher,
        localization=product.localization,
        rating=product.rating,
        edition=product.edition,
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
        plus_types=product.plus_types,
        ps_plus=bool(product.ps_plus),
        ea_access=product.ea_access,
        ps_plus_collection=product.ps_plus_collection,
        discount=product.discount,
        discount_end=product.discount_end,
        tags=product.tags,
        description=product.description,
        compound=product.compound,
        info=product.info,
        players_min=product.players_min,
        players_max=product.players_max,
        players_online=bool(product.players_online),
        has_discount=product.has_discount,
        has_ps_plus=product.has_ps_plus,
        has_ea_access=product.has_ea_access,
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
        users: Optional[Collection] = None,
        codes: Optional[Collection] = None,
        sessions: Optional[Collection] = None,
        now_provider=utcnow,
    ) -> None:
        self.users = users or get_auth_users_collection()
        self.codes = codes or get_auth_codes_collection()
        self.sessions = sessions or get_auth_sessions_collection()
        self.now_provider = now_provider

    def get_dashboard(self, db: Session) -> AdminDashboardResponse:
        users_summary = self._build_user_summary()
        products_summary = self._build_product_summary(db)
        purchases_summary = self._build_purchase_summary(db)

        recent_user_docs = list(self.users.find({}).sort("updated_at", DESCENDING).limit(8))
        recent_user_ids = [str(doc.get("_id")) for doc in recent_user_docs]
        purchase_stats = self._get_purchase_stats_for_users(db, recent_user_ids)
        recent_users = [
            build_admin_user_record(
                doc,
                purchase_count=purchase_stats.get(str(doc.get("_id")), {}).get("purchase_count", 0),
                total_spent_rub=purchase_stats.get(str(doc.get("_id")), {}).get("total_spent_rub", 0.0),
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
        query = self._build_user_query(search=search, role=role, is_active=is_active)

        total = self.users.count_documents(query)
        skip = max(page - 1, 0) * limit
        user_docs = list(self.users.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit))

        purchase_stats = self._get_purchase_stats_for_users(
            db,
            [str(doc.get("_id")) for doc in user_docs],
        )

        return AdminUserListResponse(
            users=[
                build_admin_user_record(
                    doc,
                    purchase_count=purchase_stats.get(str(doc.get("_id")), {}).get("purchase_count", 0),
                    total_spent_rub=purchase_stats.get(str(doc.get("_id")), {}).get("total_spent_rub", 0.0),
                )
                for doc in user_docs
            ],
            total=total,
            page=page,
            limit=limit,
        )

    def create_user(self, payload: AdminUserCreateRequest) -> AdminUserRecord:
        current_time = self.now_provider()

        user_doc = {
            "email": payload.email,
            "email_normalized": payload.email,
            "password_hash": hash_password(payload.password) if payload.password else None,
            "email_verified": bool(payload.email and payload.email_verified),
            "username": payload.username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "telegram_id": payload.telegram_id,
            "preferred_region": payload.preferred_region,
            "show_ukraine_prices": payload.preferred_region == "UA",
            "show_turkey_prices": payload.preferred_region == "TR",
            "show_india_prices": payload.preferred_region == "IN",
            "payment_email": payload.payment_email,
            "platform": payload.platform,
            "psn_email": payload.psn_email,
            "role": resolve_site_user_role(payload.role, telegram_id=payload.telegram_id),
            "psn_accounts": {},
            "is_active": bool(payload.is_active),
            "auth_providers": [],
            "created_at": current_time,
            "updated_at": current_time,
            "last_login_at": None,
            "last_registration_at": current_time,
            "registration_user_agent": "admin-panel",
            "registration_ip_address": None,
        }

        try:
            result = self.users.insert_one(user_doc)
            stored_user = self.users.find_one({"_id": result.inserted_id})
        except DuplicateKeyError as error:
            raise _map_duplicate_key_error(error) from error
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        if not stored_user:
            raise AuthServiceError(500, "Не удалось создать пользователя.")

        return build_admin_user_record(stored_user)

    def update_user(
        self,
        user_id: str,
        payload: AdminUserUpdateRequest,
        *,
        current_admin: SiteUserPublic,
    ) -> AdminUserRecord:
        resolved_user_id = resolve_user_identifier(user_id)
        existing_user = self.users.find_one({"_id": resolved_user_id})
        if not existing_user:
            raise AuthServiceError(404, "Пользователь не найден.")

        is_self = str(existing_user.get("_id")) == current_admin.id
        is_env_admin = is_env_admin_telegram_id(existing_user.get("telegram_id"))
        next_telegram_id = payload.telegram_id if payload.telegram_id is not None else existing_user.get("telegram_id")
        next_role = (
            resolve_site_user_role(payload.role, telegram_id=next_telegram_id)
            if payload.role is not None or payload.telegram_id is not None
            else resolve_site_user_role(existing_user.get("role"), telegram_id=next_telegram_id)
        )

        if is_env_admin and next_role != SITE_ROLE_ADMIN:
            raise AuthServiceError(400, "Администратор из .env должен оставаться администратором.")
        if is_self and next_role != SITE_ROLE_ADMIN:
            raise AuthServiceError(400, "Нельзя снять роль администратора у самого себя.")
        if is_self and payload.is_active is False:
            raise AuthServiceError(400, "Нельзя деактивировать собственный аккаунт администратора.")

        update_fields: dict[str, Any] = {
            "updated_at": self.now_provider(),
            "role": next_role,
        }

        if payload.email is not None:
            email_changed = payload.email != existing_user.get("email_normalized")
            update_fields["email"] = payload.email
            update_fields["email_normalized"] = payload.email
            if payload.email_verified is not None:
                update_fields["email_verified"] = payload.email_verified
            elif email_changed:
                update_fields["email_verified"] = False
        elif payload.email_verified is not None:
            update_fields["email_verified"] = payload.email_verified

        if payload.password:
            update_fields["password_hash"] = hash_password(payload.password)
        if payload.username is not None:
            update_fields["username"] = payload.username
        if payload.first_name is not None:
            update_fields["first_name"] = payload.first_name
        if payload.last_name is not None:
            update_fields["last_name"] = payload.last_name
        if payload.telegram_id is not None:
            update_fields["telegram_id"] = payload.telegram_id
        if payload.payment_email is not None:
            update_fields["payment_email"] = payload.payment_email
        if payload.platform is not None:
            update_fields["platform"] = payload.platform
        if payload.psn_email is not None:
            update_fields["psn_email"] = payload.psn_email
        if payload.is_active is not None:
            update_fields["is_active"] = payload.is_active

        preferred_region = payload.preferred_region or existing_user.get("preferred_region", "TR")
        if payload.preferred_region is not None:
            update_fields["preferred_region"] = preferred_region
            update_fields["show_ukraine_prices"] = preferred_region == "UA"
            update_fields["show_turkey_prices"] = preferred_region == "TR"
            update_fields["show_india_prices"] = preferred_region == "IN"

        try:
            self.users.update_one({"_id": existing_user["_id"]}, {"$set": update_fields})
            stored_user = self.users.find_one({"_id": existing_user["_id"]})
        except DuplicateKeyError as error:
            raise _map_duplicate_key_error(error) from error
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        if not stored_user:
            raise AuthServiceError(404, "Пользователь не найден после обновления.")

        return build_admin_user_record(stored_user)

    def delete_user(self, user_id: str, *, current_admin: SiteUserPublic) -> None:
        resolved_user_id = resolve_user_identifier(user_id)
        existing_user = self.users.find_one({"_id": resolved_user_id})
        if not existing_user:
            raise AuthServiceError(404, "Пользователь не найден.")

        if str(existing_user.get("_id")) == current_admin.id:
            raise AuthServiceError(400, "Нельзя удалить собственный аккаунт администратора.")
        if is_env_admin_telegram_id(existing_user.get("telegram_id")):
            raise AuthServiceError(400, "Нельзя удалить администратора из .env.")

        try:
            self.users.delete_one({"_id": existing_user["_id"]})
            self.sessions.delete_many({"user_id": existing_user["_id"]})
            if existing_user.get("email_normalized"):
                self.codes.delete_many({"email_normalized": existing_user["email_normalized"]})
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

    def list_products(
        self,
        db: Session,
        *,
        page: int = 1,
        limit: int = 24,
        search: Optional[str] = None,
        region: Optional[str] = None,
        category: Optional[str] = None,
    ) -> AdminProductListResponse:
        query = db.query(Product)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Product.id.ilike(pattern),
                    Product.name.ilike(pattern),
                    Product.main_name.ilike(pattern),
                )
            )
        if region:
            query = query.filter(Product.region == region.strip().upper())
        if category:
            query = query.filter(Product.category == category.strip())

        total = query.count()
        products = (
            query.order_by(Product.main_name.asc(), Product.name.asc(), Product.region.asc())
            .offset(max(page - 1, 0) * limit)
            .limit(limit)
            .all()
        )

        return AdminProductListResponse(
            products=[build_admin_product_record(product) for product in products],
            total=total,
            page=page,
            limit=limit,
        )

    def get_product(self, db: Session, *, product_id: str, region: str) -> AdminProductRecord:
        product = self._get_product_or_error(db, product_id=product_id, region=region)
        return build_admin_product_record(product)

    def create_product(self, db: Session, payload: AdminProductCreateRequest) -> AdminProductRecord:
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
        return build_admin_product_record(product)

    def update_product(
        self,
        db: Session,
        *,
        product_id: str,
        region: str,
        payload: AdminProductUpdateRequest,
    ) -> AdminProductRecord:
        product = self._get_product_or_error(db, product_id=product_id, region=region)
        self._apply_product_payload(product, payload)
        db.add(product)
        db.commit()
        db.refresh(product)
        return build_admin_product_record(product)

    def delete_product(self, db: Session, *, product_id: str, region: str) -> None:
        product = self._get_product_or_error(db, product_id=product_id, region=region)
        db.delete(product)
        db.commit()

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

    def _build_user_query(
        self,
        *,
        search: Optional[str],
        role: Optional[str],
        is_active: Optional[bool],
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}

        if role:
            normalized_role = resolve_site_user_role(role)
            if normalized_role == SITE_ROLE_ADMIN and settings.ADMIN_TELEGRAM_IDS:
                query["$or"] = [
                    {"role": SITE_ROLE_ADMIN},
                    {"telegram_id": {"$in": settings.ADMIN_TELEGRAM_IDS}},
                ]
            elif normalized_role == SITE_ROLE_CLIENT and settings.ADMIN_TELEGRAM_IDS:
                query["$and"] = [
                    {
                        "$or": [
                            {"role": SITE_ROLE_CLIENT},
                            {"role": {"$exists": False}},
                        ]
                    },
                    {"telegram_id": {"$nin": settings.ADMIN_TELEGRAM_IDS}},
                ]
            else:
                query["role"] = normalized_role

        if is_active is not None:
            query["is_active"] = bool(is_active)

        if search:
            search = search.strip()
            regex = {"$regex": re.escape(search), "$options": "i"}
            search_conditions: list[dict[str, Any]] = [
                {"email": regex},
                {"username": regex},
                {"first_name": regex},
                {"last_name": regex},
            ]
            if search.isdigit():
                search_conditions.append({"telegram_id": int(search)})

            if "$or" in query or "$and" in query:
                query = {"$and": [query, {"$or": search_conditions}]}
            else:
                query["$or"] = search_conditions

        return query

    def _build_user_summary(self) -> AdminUserSummary:
        total = self.users.count_documents({})
        active = self.users.count_documents({"is_active": True})
        verified = self.users.count_documents({"email_verified": True})

        admin_query: dict[str, Any]
        if settings.ADMIN_TELEGRAM_IDS:
            admin_query = {
                "$or": [
                    {"role": SITE_ROLE_ADMIN},
                    {"telegram_id": {"$in": settings.ADMIN_TELEGRAM_IDS}},
                ]
            }
        else:
            admin_query = {"role": SITE_ROLE_ADMIN}

        admins = self.users.count_documents(admin_query)
        clients = max(total - admins, 0)

        return AdminUserSummary(
            total=total,
            active=active,
            verified=verified,
            admins=admins,
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
