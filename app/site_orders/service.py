from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from sqlalchemy.orm import Session

from app.api.payment import PaymentAPIError, payment_api
from app.api.payment_india import IndiaPaymentAPIError, india_payment_api
from app.api.payment_turkey import TurkeyPaymentAPIError, turkey_payment_api
from app.api.payment_ukraine import UkrainePaymentAPIError, ukraine_payment_api
from app.auth.exceptions import AuthServiceError
from app.auth.mongo import get_auth_users_collection
from app.auth.service import resolve_user_identifier
from app.models.currency_rate import CurrencyRate
from app.models.product import Product
from app.models.purchase_order import SitePurchaseOrder
from app.utils.encryption import decrypt_password, encrypt_password
from config.settings import settings

from .schemas import PurchaseOrderResponse


ORDER_STATUS_LABELS = {
    "payment_pending": "Ожидает оплату",
    "payment_review": "Платеж на проверке",
    "fulfilled": "Выдан",
    "cancelled": "Отменён",
}

REGION_ALIASES = {
    "EN-UA": "UA",
    "UA": "UA",
    "UAH": "UA",
    "EN-TR": "TR",
    "TR": "TR",
    "TRY": "TR",
    "EN-IN": "IN",
    "IN": "IN",
    "INR": "IN",
}

REGION_PRICE_FIELDS = {
    "TR": ("price_try", "ps_plus_price_try"),
    "UA": ("price_uah", "ps_plus_price_uah"),
    "IN": ("price_inr", "ps_plus_price_inr"),
}


@dataclass
class CheckoutProfileContext:
    payment_email: str
    platform: Optional[str]
    psn_email: str
    psn_password: str
    backup_code: str


@dataclass
class CheckoutInputOverrides:
    purchase_email: Optional[str] = None
    platform: Optional[str] = None
    psn_email: Optional[str] = None
    psn_password: Optional[str] = None
    backup_code: Optional[str] = None


@dataclass
class PaymentGenerationResult:
    payment_url: str
    payment_provider: str
    payment_type: str
    product_name: str
    platform: Optional[str]
    psn_email: str
    price: float
    price_rub: float
    currency: str
    region: str
    payment_metadata: dict[str, Any]


def utcnow() -> datetime:
    return datetime.utcnow()


def normalize_region(region: str) -> str:
    normalized = REGION_ALIASES.get((region or "").strip().upper())
    if not normalized:
        raise AuthServiceError(422, "Недопустимый регион покупки.")
    return normalized


def build_status_label(status: str) -> str:
    return ORDER_STATUS_LABELS.get(status, status)


def generate_order_number(*, now: Optional[datetime] = None) -> str:
    current_time = now or utcnow()
    return f"PS-{current_time:%Y%m%d}-{secrets.token_hex(3).upper()}"


def _decrypt_region_secret(account: dict[str, Any], hash_key: str, salt_key: str) -> str:
    encrypted_value = account.get(hash_key)
    salt_value = account.get(salt_key)
    if not encrypted_value or not salt_value:
        return ""
    return decrypt_password(encrypted_value, salt_value)


def _resolve_psn_account(user_doc: dict[str, Any], region: str) -> dict[str, Any]:
    accounts = dict(user_doc.get("psn_accounts") or {})
    region_account = dict(accounts.get(region) or {})

    if region == "UA" and not region_account and (user_doc.get("psn_email") or user_doc.get("platform")):
        region_account = {
            "platform": user_doc.get("platform"),
            "psn_email": user_doc.get("psn_email"),
        }

    return region_account


def build_checkout_profile_context(
    user_doc: dict[str, Any],
    region: str,
    *,
    overrides: Optional[CheckoutInputOverrides] = None,
) -> CheckoutProfileContext:
    current_overrides = overrides or CheckoutInputOverrides()
    payment_email = current_overrides.purchase_email or (user_doc.get("payment_email") or "").strip().lower()
    missing_fields: list[str] = []
    if not payment_email:
        missing_fields.append("purchase_email")

    if region in {"TR", "IN"}:
        if missing_fields:
            raise AuthServiceError(
                400,
                "Заполните недостающие данные для покупки.",
                extra={"missing_fields": missing_fields},
            )

        return CheckoutProfileContext(
            payment_email=payment_email,
            platform=(current_overrides.platform or user_doc.get("platform") or "PS5"),
            psn_email="",
            psn_password="",
            backup_code="",
        )

    region_account = _resolve_psn_account(user_doc, region)
    platform = current_overrides.platform or region_account.get("platform") or user_doc.get("platform") or "PS5"
    psn_email = current_overrides.psn_email or (region_account.get("psn_email") or user_doc.get("psn_email") or "").strip().lower()
    psn_password = current_overrides.psn_password or _decrypt_region_secret(region_account, "psn_password_hash", "psn_password_salt")
    backup_code = current_overrides.backup_code or ""

    if not psn_email:
        missing_fields.append("psn_email")
    if not psn_password:
        missing_fields.append("psn_password")
    if missing_fields:
        raise AuthServiceError(
            400,
            "Заполните недостающие данные для покупки.",
            extra={"missing_fields": missing_fields},
        )

    return CheckoutProfileContext(
        payment_email=payment_email,
        platform=platform,
        psn_email=psn_email,
        psn_password=psn_password,
        backup_code=backup_code,
    )


def resolve_product_price(product: Product, *, region: str, use_ps_plus: bool) -> float:
    price_field, ps_plus_field = REGION_PRICE_FIELDS.get(region, (None, None))
    if not price_field:
        raise AuthServiceError(422, "Для товара не найдено ценовое поле региона.")

    current_price = None
    if use_ps_plus and ps_plus_field:
        ps_plus_price = getattr(product, ps_plus_field, None)
        if ps_plus_price and ps_plus_price > 0:
            current_price = ps_plus_price

    if not current_price:
        current_price = getattr(product, price_field, None)

    if not current_price or current_price <= 0:
        raise AuthServiceError(400, f"Для товара не установлена цена в регионе {region}.")

    return float(current_price)


def serialize_purchase_order(order: SitePurchaseOrder) -> PurchaseOrderResponse:
    delivery = None
    delivery_items = order.get_delivery_items()
    if order.delivery_title or order.delivery_message or delivery_items:
        delivery = {
            "title": order.delivery_title,
            "message": order.delivery_message,
            "items": delivery_items,
        }

    return PurchaseOrderResponse(
        order_number=order.order_number,
        status=order.status,
        status_label=build_status_label(order.status),
        product_id=order.product_id,
        product_name=order.product_name,
        product_region=order.product_region,
        product_image=order.product_image,
        product_platforms=order.product_platforms,
        currency_code=order.currency_code,
        local_price=order.local_price,
        price_rub=order.price_rub,
        use_ps_plus=bool(order.use_ps_plus),
        payment_email=order.payment_email,
        psn_email=order.psn_email,
        platform=order.platform,
        payment_provider=order.payment_provider,
        payment_type=order.payment_type,
        payment_url=order.payment_url,
        payment_metadata=order.get_payment_metadata(),
        manager_contact_url=order.manager_contact_url,
        status_note=order.status_note,
        delivery=delivery,
        created_at=order.created_at,
        updated_at=order.updated_at,
        payment_submitted_at=order.payment_submitted_at,
        fulfilled_at=order.fulfilled_at,
    )


class SitePurchaseService:
    def __init__(
        self,
        *,
        users_collection: Optional[Collection] = None,
        now_provider=utcnow,
    ) -> None:
        self.users_collection = users_collection or get_auth_users_collection()
        self.now_provider = now_provider

    def get_user_doc(self, user_id: Any) -> dict[str, Any]:
        resolved_user_id = resolve_user_identifier(user_id)
        try:
            user_doc = self.users_collection.find_one({"_id": resolved_user_id, "is_active": True})
        except (PyMongoError, InvalidId) as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        if not user_doc:
            raise AuthServiceError(404, "Профиль пользователя не найден.")
        return user_doc

    async def create_checkout(
        self,
        db: Session,
        *,
        site_user_id: str,
        product_id: str,
        region: str,
        use_ps_plus: bool,
        purchase_email: Optional[str] = None,
        platform: Optional[str] = None,
        psn_email: Optional[str] = None,
        psn_password: Optional[str] = None,
        backup_code: Optional[str] = None,
    ) -> PurchaseOrderResponse:
        user_doc = self.get_user_doc(site_user_id)
        normalized_region = normalize_region(region)
        product = db.query(Product).filter(Product.id == product_id, Product.region == normalized_region).first()
        if not product:
            raise AuthServiceError(404, f"Товар не найден в регионе {normalized_region}.")

        profile_context = build_checkout_profile_context(
            user_doc,
            normalized_region,
            overrides=CheckoutInputOverrides(
                purchase_email=purchase_email,
                platform=platform,
                psn_email=psn_email,
                psn_password=psn_password,
                backup_code=backup_code,
            ),
        )
        self._persist_checkout_profile(
            site_user_id=site_user_id,
            user_doc=user_doc,
            region=normalized_region,
            profile_context=profile_context,
            overrides=CheckoutInputOverrides(
                purchase_email=purchase_email,
                platform=platform,
                psn_email=psn_email,
                psn_password=psn_password,
                backup_code=backup_code,
            ),
        )
        current_price = resolve_product_price(product, region=normalized_region, use_ps_plus=use_ps_plus)
        region_info = product.get_region_info()
        rate = CurrencyRate.get_rate_for_price(db, region_info["code"], current_price)
        price_rub = round(current_price * rate, 2)

        payment_result = await self._generate_payment(
            product=product,
            profile_context=profile_context,
            current_price=current_price,
            price_rub=price_rub,
        )

        current_time = self.now_provider()
        order = SitePurchaseOrder(
            order_number=self._generate_unique_order_number(db, now=current_time),
            site_user_id=str(user_doc["_id"]),
            user_email=user_doc.get("email"),
            user_display_name=(user_doc.get("first_name") or user_doc.get("username") or user_doc.get("email")),
            product_id=product.id,
            product_region=normalized_region,
            product_name=payment_result.product_name,
            product_image=product.image,
            product_platforms=product.platforms,
            currency_code=payment_result.currency,
            local_price=payment_result.price,
            price_rub=payment_result.price_rub,
            use_ps_plus=use_ps_plus,
            payment_email=profile_context.payment_email,
            psn_email=payment_result.psn_email or None,
            platform=payment_result.platform,
            payment_provider=payment_result.payment_provider,
            payment_type=payment_result.payment_type,
            payment_url=payment_result.payment_url,
            status="payment_pending",
            manager_contact_url=settings.MANAGER_TELEGRAM_URL or None,
            created_at=current_time,
            updated_at=current_time,
        )
        order.set_payment_metadata(payment_result.payment_metadata)

        db.add(order)
        db.commit()
        db.refresh(order)
        return serialize_purchase_order(order)

    def _persist_checkout_profile(
        self,
        *,
        site_user_id: str,
        user_doc: dict[str, Any],
        region: str,
        profile_context: CheckoutProfileContext,
        overrides: CheckoutInputOverrides,
    ) -> None:
        current_time = self.now_provider()
        resolved_user_id = resolve_user_identifier(site_user_id)
        update_fields: dict[str, Any] = {}

        if profile_context.payment_email and profile_context.payment_email != user_doc.get("payment_email"):
            update_fields["payment_email"] = profile_context.payment_email

        if region == "UA":
            existing_accounts = dict(user_doc.get("psn_accounts") or {})
            region_account = _resolve_psn_account(user_doc, region)
            account_changed = False

            if profile_context.platform and region_account.get("platform") != profile_context.platform:
                region_account["platform"] = profile_context.platform
                update_fields["platform"] = profile_context.platform
                account_changed = True

            if profile_context.psn_email and region_account.get("psn_email") != profile_context.psn_email:
                region_account["psn_email"] = profile_context.psn_email
                update_fields["psn_email"] = profile_context.psn_email
                account_changed = True

            if overrides.psn_password:
                encoded_password, password_salt = encrypt_password(overrides.psn_password)
                region_account["psn_password_hash"] = encoded_password
                region_account["psn_password_salt"] = password_salt
                account_changed = True

            if "backup_code_hash" in region_account:
                region_account.pop("backup_code_hash", None)
                account_changed = True
            if "backup_code_salt" in region_account:
                region_account.pop("backup_code_salt", None)
                account_changed = True

            if account_changed:
                region_account["updated_at"] = current_time
                existing_accounts[region] = region_account
                update_fields["psn_accounts"] = existing_accounts

        if not update_fields:
            return

        update_fields["updated_at"] = current_time

        try:
            self.users_collection.update_one({"_id": resolved_user_id}, {"$set": update_fields})
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

    def list_user_orders(
        self,
        db: Session,
        *,
        site_user_id: str,
        days: Optional[int] = None,
    ) -> list[PurchaseOrderResponse]:
        query = db.query(SitePurchaseOrder).filter(SitePurchaseOrder.site_user_id == site_user_id)

        if days is not None:
            threshold = self.now_provider() - timedelta(days=days)
            query = query.filter(SitePurchaseOrder.created_at >= threshold)

        orders = query.order_by(SitePurchaseOrder.created_at.desc(), SitePurchaseOrder.id.desc()).all()
        return [serialize_purchase_order(order) for order in orders]

    def confirm_payment(self, db: Session, *, site_user_id: str, order_number: str) -> PurchaseOrderResponse:
        order = self._get_user_order(db, site_user_id=site_user_id, order_number=order_number)
        if order.status == "fulfilled":
            return serialize_purchase_order(order)

        current_time = self.now_provider()
        order.status = "payment_review"
        order.payment_submitted_at = current_time
        order.updated_at = current_time
        db.add(order)
        db.commit()
        db.refresh(order)
        return serialize_purchase_order(order)

    def list_all_orders(self, db: Session, *, limit: int = 100) -> list[PurchaseOrderResponse]:
        orders = (
            db.query(SitePurchaseOrder)
            .order_by(SitePurchaseOrder.created_at.desc(), SitePurchaseOrder.id.desc())
            .limit(limit)
            .all()
        )
        return [serialize_purchase_order(order) for order in orders]

    def fulfill_order(
        self,
        db: Session,
        *,
        order_number: str,
        delivery_title: Optional[str],
        delivery_message: Optional[str],
        delivery_items: list[dict[str, str]],
        status_note: Optional[str],
    ) -> PurchaseOrderResponse:
        order = db.query(SitePurchaseOrder).filter(SitePurchaseOrder.order_number == order_number).first()
        if not order:
            raise AuthServiceError(404, "Заказ не найден.")

        current_time = self.now_provider()
        order.status = "fulfilled"
        order.delivery_title = delivery_title or "Данные по заказу"
        order.delivery_message = delivery_message
        order.status_note = status_note
        order.payment_submitted_at = order.payment_submitted_at or current_time
        order.fulfilled_at = current_time
        order.updated_at = current_time
        order.set_delivery_items(delivery_items)

        db.add(order)
        db.commit()
        db.refresh(order)
        return serialize_purchase_order(order)

    def _get_user_order(self, db: Session, *, site_user_id: str, order_number: str) -> SitePurchaseOrder:
        order = (
            db.query(SitePurchaseOrder)
            .filter(
                SitePurchaseOrder.order_number == order_number,
                SitePurchaseOrder.site_user_id == site_user_id,
            )
            .first()
        )
        if not order:
            raise AuthServiceError(404, "Заказ не найден.")
        return order

    def _generate_unique_order_number(self, db: Session, *, now: datetime) -> str:
        for _ in range(10):
            order_number = generate_order_number(now=now)
            exists = db.query(SitePurchaseOrder).filter(SitePurchaseOrder.order_number == order_number).first()
            if not exists:
                return order_number
        raise AuthServiceError(500, "Не удалось создать номер заказа.")

    async def _generate_payment(
        self,
        *,
        product: Product,
        profile_context: CheckoutProfileContext,
        current_price: float,
        price_rub: float,
    ) -> PaymentGenerationResult:
        game_name = product.name or product.get_display_name()
        region_info = product.get_region_info()
        region = product.region

        try:
            if region == "IN":
                payment_url, purchase_info = await india_payment_api.get_payment_url(
                    game_price_inr=current_price,
                    need_registration=False,
                )
                card_price_rub = await india_payment_api.get_purchase_price_rub(
                    purchase_info,
                    payment_url=payment_url,
                )
                direct_card_url = india_payment_api.get_direct_payment_url(
                    buyer_email=profile_context.payment_email,
                    quantity=purchase_info.total_cards,
                )
                payment_metadata = {
                    "india_payment": True,
                    "card_info": {
                        "total_value": purchase_info.total_value,
                        "game_price": purchase_info.game_price,
                        "remaining_balance": purchase_info.remaining_balance,
                        "cards": purchase_info.quantity_map,
                        "total_cards": purchase_info.total_cards,
                        "message_ru": purchase_info.get_description_ru(),
                        "message_en": purchase_info.get_description_en(),
                        "card_price_rub": card_price_rub,
                        "direct_card_url": direct_card_url,
                    },
                }
                return PaymentGenerationResult(
                    payment_url=self._append_email_to_url(payment_url, profile_context.payment_email, quantity=purchase_info.total_cards),
                    payment_provider="oplata",
                    payment_type="topup",
                    product_name=game_name,
                    platform=profile_context.platform,
                    psn_email="",
                    price=float(purchase_info.total_value),
                    price_rub=float(card_price_rub or price_rub),
                    currency=region_info["code"],
                    region=region,
                    payment_metadata=payment_metadata,
                )

            if region == "UA":
                payment_url, payment_info = await ukraine_payment_api.get_payment_url(
                    game=game_name,
                    email=profile_context.psn_email,
                    password=profile_context.psn_password,
                    uah_price=current_price,
                    twofa_code=profile_context.backup_code,
                )
                card_price_rub = await ukraine_payment_api.get_payment_price_rub_from_url(payment_url)
                direct_card_url = ukraine_payment_api.get_direct_payment_url(profile_context.payment_email)
                payment_metadata = {
                    "ukraine_payment": True,
                    "topup_info": {
                        "game_price": payment_info.game_price,
                        "topup_amount": payment_info.topup_amount,
                        "card_price_rub": card_price_rub,
                        "remaining_balance": payment_info.remaining_balance,
                        "message_ru": payment_info.get_description_ru(),
                        "message_en": payment_info.get_description_en(),
                        "direct_card_url": direct_card_url,
                    },
                }
                return PaymentGenerationResult(
                    payment_url=self._append_email_to_url(payment_url, profile_context.payment_email),
                    payment_provider="oplata",
                    payment_type="account_purchase",
                    product_name=game_name,
                    platform=profile_context.platform,
                    psn_email=profile_context.psn_email,
                    price=float(payment_info.topup_amount),
                    price_rub=float(card_price_rub or price_rub),
                    currency=region_info["code"],
                    region=region,
                    payment_metadata=payment_metadata,
                )

            if region == "TR":
                payment_url, purchase_info = await turkey_payment_api.get_payment_url(
                    game_price_tl=current_price,
                    need_registration=False,
                )
                card_price_rub = await turkey_payment_api.get_purchase_price_rub(
                    purchase_info,
                    payment_url=payment_url,
                )
                direct_card_url = turkey_payment_api.get_direct_payment_url(
                    buyer_email=profile_context.payment_email,
                    quantity=purchase_info.total_cards,
                )
                payment_metadata = {
                    "turkey_payment": True,
                    "card_info": {
                        "total_value": purchase_info.total_value,
                        "game_price": purchase_info.game_price,
                        "remaining_balance": purchase_info.remaining_balance,
                        "cards": purchase_info.quantity_map,
                        "total_cards": purchase_info.total_cards,
                        "message_ru": purchase_info.get_description_ru(),
                        "message_en": purchase_info.get_description_en(),
                        "card_price_rub": card_price_rub,
                        "direct_card_url": direct_card_url,
                    },
                }
                return PaymentGenerationResult(
                    payment_url=self._append_email_to_url(payment_url, profile_context.payment_email, quantity=purchase_info.total_cards),
                    payment_provider="oplata",
                    payment_type="topup",
                    product_name=game_name,
                    platform=profile_context.platform,
                    psn_email="",
                    price=float(purchase_info.total_value),
                    price_rub=float(card_price_rub or price_rub),
                    currency=region_info["code"],
                    region=region,
                    payment_metadata=payment_metadata,
                )

            payment_url = await payment_api.get_payment_url(
                platform=profile_context.platform or "PS5",
                game=game_name,
                email=profile_context.psn_email,
                password=profile_context.psn_password,
                price=price_rub,
                trl_price=current_price,
                twofa_code=profile_context.backup_code,
            )
            return PaymentGenerationResult(
                payment_url=payment_url,
                payment_provider="digiseller",
                payment_type="account_purchase",
                product_name=game_name,
                platform=profile_context.platform,
                psn_email=profile_context.psn_email,
                price=current_price,
                price_rub=price_rub,
                currency=region_info["code"],
                region=region,
                payment_metadata={},
            )
        except (PaymentAPIError, IndiaPaymentAPIError, TurkeyPaymentAPIError, UkrainePaymentAPIError) as error:
            raise AuthServiceError(500, f"Не удалось подготовить ссылку на оплату: {error}") from error

    @staticmethod
    def _append_email_to_url(payment_url: str, payment_email: str, *, quantity: Optional[int] = None) -> str:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(payment_url)
        query_params = parse_qs(parsed.query)
        if payment_email:
            query_params["email"] = [payment_email]

        if quantity and quantity > 1:
            for field_name in ("n", "cnt", "product_cnt", "product_cnt_set", "quantity"):
                query_params[field_name] = [str(quantity)]

        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))


_site_purchase_service: Optional[SitePurchaseService] = None


def get_site_purchase_service() -> SitePurchaseService:
    global _site_purchase_service
    if _site_purchase_service is None:
        _site_purchase_service = SitePurchaseService()
    return _site_purchase_service
