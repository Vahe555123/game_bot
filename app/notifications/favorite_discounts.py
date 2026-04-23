from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence
from urllib.parse import quote

from sqlalchemy.orm import Session, joinedload

from app.auth.email_service import EmailDeliveryError, email_is_configured
from app.models import (
    FavoriteDiscountNotification,
    Product,
    SitePurchaseOrder,
    UserFavoriteProduct,
)
from app.site_orders.email_service import send_favorite_discount_email
from app.utils.time import utcnow
from config.settings import settings

logger = logging.getLogger(__name__)

REGION_LABELS = {
    "UA": "Украина",
    "TR": "Турция",
    "IN": "Индия",
}

REGION_CURRENCY = {
    "UA": ("price_uah", "old_price_uah", "UAH"),
    "TR": ("price_try", "old_price_try", "TRY"),
    "IN": ("price_inr", "old_price_inr", "INR"),
}


class NoNotificationRecipient(RuntimeError):
    """Raised when a user has no email and no Telegram chat id."""


@dataclass
class FavoriteDiscountNotificationSummary:
    candidates: int = 0
    sent: int = 0
    skipped_existing: int = 0
    no_recipient: int = 0
    failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _chunks(values: Sequence[str], size: int = 500) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield list(values[index:index + size])


def _positive_float(value) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _clean_email(value: str | None) -> str | None:
    cleaned = (value or "").strip().lower()
    if not cleaned or "@" not in cleaned:
        return None
    return cleaned


def _region(product: Product) -> str:
    return (product.region or "").strip().upper()


def _price_values(product: Product) -> tuple[float | None, float | None, str]:
    region = _region(product)
    price_field, old_price_field, currency = REGION_CURRENCY.get(region, ("price", "old_price", "RUB"))
    current_price = _positive_float(getattr(product, price_field, None)) or _positive_float(product.price)
    old_price = _positive_float(getattr(product, old_price_field, None)) or _positive_float(product.old_price)
    return current_price, old_price, currency


def _discount_percent(product: Product) -> int | None:
    for value in (product.discount, getattr(product, "discount_percent", None)):
        parsed = _positive_float(value)
        if parsed:
            return int(round(parsed))

    current_price, old_price, _currency = _price_values(product)
    if current_price and old_price and old_price > current_price:
        return int(round(((old_price - current_price) / old_price) * 100))
    return None


def _is_discounted(product: Product) -> bool:
    current_price, old_price, _currency = _price_values(product)
    discount = _discount_percent(product)
    if not current_price:
        return False
    if discount and discount > 0:
        return True
    return bool(old_price and old_price > current_price)


def _discount_signature(product: Product) -> str:
    current_price, old_price, currency = _price_values(product)
    parts = [
        product.id,
        _region(product),
        str(_discount_percent(product) or ""),
        str(product.discount_end or ""),
        str(current_price or ""),
        str(old_price or ""),
        str(product.price_rub or ""),
        currency,
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _product_url(product: Product) -> str:
    base_url = (settings.PUBLIC_APP_URL or settings.WEBAPP_URL or "").rstrip("/")
    if not base_url:
        base_url = "http://localhost:5173"
    return f"{base_url}/catalog/{quote(product.id or '', safe='')}?region={quote(_region(product), safe='')}"


def _format_price(product: Product, *, old: bool = False) -> str | None:
    current_price, old_price, currency = _price_values(product)
    value = old_price if old else current_price
    if value is None:
        return None
    return f"{value:.2f} {currency}"


def _notification_payload(product: Product) -> dict[str, str | None]:
    discount = _discount_percent(product)
    return {
        "product_id": product.id,
        "product_name": product.get_display_name(),
        "region": _region(product),
        "region_label": f"{REGION_LABELS.get(_region(product), _region(product))} ({_region(product)})",
        "discount_text": f"-{discount}%" if discount else "Скидка",
        "price_text": _format_price(product),
        "old_price_text": _format_price(product, old=True),
        "discount_end": product.discount_end,
        "product_url": _product_url(product),
    }


def _telegram_text(payload: dict[str, str | None]) -> str:
    lines = [
        "Скидка на игру из избранного",
        "",
        str(payload.get("product_name") or "Товар"),
        f"Регион: {payload.get('region_label') or payload.get('region') or '-'}",
        f"Скидка: {payload.get('discount_text') or '-'}",
        f"Цена сейчас: {payload.get('price_text') or '-'}",
    ]
    if payload.get("old_price_text"):
        lines.append(f"Цена до скидки: {payload['old_price_text']}")
    if payload.get("discount_end"):
        lines.append(f"Действует до: {payload['discount_end']}")
    if payload.get("product_url"):
        lines.extend(["", str(payload["product_url"])])
    return "\n".join(lines)


def _select_best_discounted_products(products: Iterable[Product]) -> dict[str, Product]:
    best_by_product_id: dict[str, Product] = {}
    for product in products:
        if not product.id or not _is_discounted(product):
            continue

        existing = best_by_product_id.get(product.id)
        if existing is None:
            best_by_product_id[product.id] = product
            continue

        current_discount = _discount_percent(product) or 0
        existing_discount = _discount_percent(existing) or 0
        if current_discount > existing_discount:
            best_by_product_id[product.id] = product

    return best_by_product_id


def _ensure_notification_table(db: Session) -> None:
    FavoriteDiscountNotification.__table__.create(bind=db.get_bind(), checkfirst=True)


def _already_sent(db: Session, *, user_id: int, product_id: str, signature: str) -> bool:
    return bool(
        db.query(FavoriteDiscountNotification.id)
        .filter(
            FavoriteDiscountNotification.user_id == user_id,
            FavoriteDiscountNotification.product_id == product_id,
            FavoriteDiscountNotification.discount_signature == signature,
            FavoriteDiscountNotification.status == "sent",
        )
        .first()
    )


def _latest_purchase_email(db: Session, user_id: int) -> str | None:
    order = (
        db.query(SitePurchaseOrder)
        .filter(
            SitePurchaseOrder.site_user_id == str(user_id),
            SitePurchaseOrder.payment_email.isnot(None),
            SitePurchaseOrder.payment_email != "",
        )
        .order_by(SitePurchaseOrder.updated_at.desc(), SitePurchaseOrder.id.desc())
        .first()
    )
    return _clean_email(order.payment_email if order else None)


def _preferred_email(db: Session, user) -> str | None:
    return (
        _clean_email(getattr(user, "payment_email", None))
        or _latest_purchase_email(db, int(user.id))
        or _clean_email(getattr(user, "email", None))
    )


async def _send_telegram(chat_id: int, text: str) -> None:
    from aiogram import Bot

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=False)
    finally:
        await bot.session.close()


async def _deliver_to_user(db: Session, user, payload: dict[str, str | None]) -> tuple[str, str]:
    email = _preferred_email(db, user)
    telegram_id = getattr(user, "telegram_id", None)

    if email and email_is_configured():
        try:
            await asyncio.to_thread(
                send_favorite_discount_email,
                email=email,
                notification_payload=payload,
            )
            return "email", email
        except Exception as error:
            if not telegram_id or not settings.TELEGRAM_BOT_TOKEN:
                raise
            logger.warning("Email discount notification failed, falling back to Telegram: %s", error)

    if telegram_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_telegram(int(telegram_id), _telegram_text(payload))
        return "telegram", str(telegram_id)

    if email:
        raise EmailDeliveryError("SMTP не настроен, Telegram для пользователя не найден.")

    raise NoNotificationRecipient("У пользователя нет email для покупок, регистрационного email или Telegram chat id.")


def _record_notification(
    db: Session,
    *,
    user_id: int,
    product: Product,
    signature: str,
    channel: str,
    recipient: str | None,
    status: str,
    error_message: str | None = None,
) -> None:
    db.add(
        FavoriteDiscountNotification(
            user_id=user_id,
            product_id=product.id,
            region=_region(product) or None,
            discount_signature=signature,
            channel=channel,
            recipient=recipient,
            status=status,
            error_message=error_message,
            sent_at=utcnow() if status == "sent" else None,
            created_at=utcnow(),
        )
    )
    db.commit()


async def notify_favorite_discounts_for_products(
    db: Session,
    products: Iterable[Product],
) -> dict[str, int]:
    _ensure_notification_table(db)
    summary = FavoriteDiscountNotificationSummary()
    discounted_products = _select_best_discounted_products(products)
    if not discounted_products:
        return summary.to_dict()

    favorites = (
        db.query(UserFavoriteProduct)
        .options(joinedload(UserFavoriteProduct.user))
        .filter(UserFavoriteProduct.product_id.in_(list(discounted_products.keys())))
        .all()
    )

    for favorite in favorites:
        user = favorite.user
        product = discounted_products.get(favorite.product_id)
        if user is None or product is None:
            continue

        summary.candidates += 1
        signature = _discount_signature(product)
        if _already_sent(db, user_id=int(user.id), product_id=product.id, signature=signature):
            summary.skipped_existing += 1
            continue

        payload = _notification_payload(product)
        try:
            channel, recipient = await _deliver_to_user(db, user, payload)
        except NoNotificationRecipient:
            summary.no_recipient += 1
            continue
        except Exception as error:
            logger.exception(
                "Failed to send favorite discount notification user_id=%s product_id=%s",
                user.id,
                product.id,
            )
            summary.failed += 1
            try:
                _record_notification(
                    db,
                    user_id=int(user.id),
                    product=product,
                    signature=signature,
                    channel="failed",
                    recipient=None,
                    status="failed",
                    error_message=f"{type(error).__name__}: {error}",
                )
            except Exception:
                logger.exception("Failed to record favorite discount notification failure")
                db.rollback()
            continue

        _record_notification(
            db,
            user_id=int(user.id),
            product=product,
            signature=signature,
            channel=channel,
            recipient=recipient,
            status="sent",
        )
        summary.sent += 1

    return summary.to_dict()


async def notify_favorite_discounts_for_product_ids(
    db: Session,
    product_ids: Iterable[str] | None,
) -> dict[str, int]:
    _ensure_notification_table(db)

    favorite_ids = {
        row[0]
        for row in db.query(UserFavoriteProduct.product_id).distinct().all()
        if row[0]
    }
    if not favorite_ids:
        return FavoriteDiscountNotificationSummary().to_dict()

    normalized_ids = {str(product_id).strip() for product_id in (product_ids or []) if str(product_id).strip()}
    if normalized_ids:
        favorite_ids &= normalized_ids
    if not favorite_ids:
        return FavoriteDiscountNotificationSummary().to_dict()

    products: list[Product] = []
    sorted_ids = sorted(favorite_ids)
    for chunk in _chunks(sorted_ids):
        products.extend(db.query(Product).filter(Product.id.in_(chunk)).all())

    return await notify_favorite_discounts_for_products(db, products)


def notify_favorite_discounts_for_products_sync(
    db: Session,
    products: Iterable[Product],
) -> dict[str, int]:
    return asyncio.run(notify_favorite_discounts_for_products(db, products))


def notify_favorite_discounts_for_product_ids_sync(
    db: Session,
    product_ids: Iterable[str] | None,
) -> dict[str, int]:
    return asyncio.run(notify_favorite_discounts_for_product_ids(db, product_ids))
