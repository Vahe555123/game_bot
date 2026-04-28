from __future__ import annotations

import asyncio
import hashlib
import html
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.auth.email_service import email_is_configured
from app.models import (
    FavoriteDiscountNotification,
    Product,
    SitePurchaseOrder,
    User,
    UserFavoriteProduct,
)
from app.site_orders.email_service import send_favorite_discount_combined_email
from app.utils.time import utcnow
from config.settings import settings

logger = logging.getLogger(__name__)

REGION_FLAG = {"UA": "🇺🇦", "TR": "🇹🇷", "IN": "🇮🇳"}
REGION_PRICE_FIELDS = {
    "UA": ("price_uah", "old_price_uah", "₴"),
    "TR": ("price_try", "old_price_try", "₺"),
    "IN": ("price_inr", "old_price_inr", "₹"),
}
REGION_RATE_FROM_RUB = {"UA": "UAH", "TR": "TRY", "IN": "INR"}
REGION_DISPLAY_ORDER = ("TR", "IN", "UA")
COMBINED_BATCH_PRODUCT_ID = "<favorites-batch>"
TG_TEXT_LIMIT = 4096
MAX_GAMES_PER_MESSAGE = 25
MIN_GAMES_PER_MESSAGE = 10

RU_MONTHS_GENITIVE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


@dataclass
class FavoriteDiscountNotificationSummary:
    candidates: int = 0
    sent: int = 0
    email_sent: int = 0
    telegram_sent: int = 0
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


def _discount_percent(product: Product) -> int | None:
    for value in (getattr(product, "discount_percent", None), product.discount):
        parsed = _positive_float(value)
        if parsed:
            return int(round(parsed))

    region = _region(product)
    fields = REGION_PRICE_FIELDS.get(region)
    if fields:
        price_field, old_price_field, _symbol = fields
        current = _positive_float(getattr(product, price_field, None))
        old = _positive_float(getattr(product, old_price_field, None))
        if current and old and old > current:
            return int(round(((old - current) / old) * 100))
    return None


def _is_discounted_product(product: Product) -> bool:
    discount = _discount_percent(product)
    if discount and discount > 0:
        return True
    region = _region(product)
    fields = REGION_PRICE_FIELDS.get(region)
    if not fields:
        return False
    price_field, old_price_field, _symbol = fields
    current = _positive_float(getattr(product, price_field, None))
    old = _positive_float(getattr(product, old_price_field, None))
    return bool(current and old and old > current)


def _format_int_amount(value: float, symbol: str) -> str:
    return f"{int(round(value))}{symbol}"


def _convert_to_rub(local_value: float, region: str) -> float | None:
    """Best-effort conversion local -> RUB.

    Avoids an import cycle: parser-side currency_converter is loaded lazily.
    """
    rate_currency = REGION_RATE_FROM_RUB.get(region)
    if not rate_currency:
        return None
    try:
        from parser import currency_converter  # type: ignore
        return float(currency_converter.convert(local_value, rate_currency, "RUB"))
    except Exception:
        return None


def _region_price_block(product: Product) -> dict | None:
    """Returns a region price block for one product row (single region in DB).

    The block is rendered for the user's notification. If the product row has no
    price data for its region, returns None — so the caller skips this region
    (we never substitute another region as a default).
    """
    region = _region(product)
    fields = REGION_PRICE_FIELDS.get(region)
    if not fields:
        return None
    price_field, old_price_field, symbol = fields
    current_local = _positive_float(getattr(product, price_field, None))
    if not current_local:
        return None
    old_local = _positive_float(getattr(product, old_price_field, None))

    current_rub = _positive_float(getattr(product, "price_rub", None)) or _convert_to_rub(current_local, region)
    old_rub = _convert_to_rub(old_local, region) if old_local else None

    has_old = bool(old_local and old_local > current_local)
    return {
        "region": region,
        "flag": REGION_FLAG.get(region, ""),
        "current_local_text": _format_int_amount(current_local, symbol),
        "old_local_text": _format_int_amount(old_local, symbol) if has_old else None,
        "current_rub_text": _format_int_amount(current_rub, "₽") if current_rub else None,
        "old_rub_text": _format_int_amount(old_rub, "₽") if has_old and old_rub else None,
        "discount_end": (product.discount_end or "").strip() or None,
    }


def _favorites_url() -> str:
    base_url = (settings.PUBLIC_APP_URL or settings.WEBAPP_URL or "").rstrip("/") or "http://localhost:5173"
    return f"{base_url}/favorites"


def _product_url(product_id: str, region: str | None) -> str:
    base_url = (settings.PUBLIC_APP_URL or settings.WEBAPP_URL or "").rstrip("/") or "http://localhost:5173"
    region_part = (region or "").strip().upper()
    suffix = f"?region={region_part}" if region_part else ""
    from urllib.parse import quote
    return f"{base_url}/catalog/{quote(product_id, safe='')}{suffix}"


def _banner_url() -> str | None:
    base_url = (settings.PUBLIC_APP_URL or "").rstrip("/")
    if not base_url:
        return None
    banner_path = Path(__file__).resolve().parents[2] / "static" / "images" / "favorite_discount_banner.png"
    if not banner_path.exists():
        return None
    return f"{base_url}/static/images/favorite_discount_banner.png"


def _format_discount_end(discount_end: str | None) -> str | None:
    if not discount_end:
        return None
    text = discount_end.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(text, fmt)
            month = RU_MONTHS_GENITIVE.get(parsed.month)
            if month:
                return f"Распродажа закончится {parsed.day} {month}."
        except ValueError:
            continue
    return f"Распродажа закончится {text}."


def _latest_discount_end(games: list[dict]) -> str | None:
    candidates: list[str] = []
    for game in games:
        for region in game.get("regions") or []:
            end = region.get("discount_end")
            if end:
                candidates.append(end)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return _format_discount_end(candidates[0])


def _build_user_games(
    *,
    favorites_in_order: list[UserFavoriteProduct],
    products_by_id: dict[str, list[Product]],
) -> list[dict]:
    """Build per-product game blocks for one user, sorted by favorited_at desc.

    Includes a product only if at least one regional row is currently discounted.
    """
    games: list[dict] = []
    seen_ids: set[str] = set()
    for favorite in favorites_in_order:
        product_id = (favorite.product_id or "").strip()
        if not product_id or product_id in seen_ids:
            continue
        regional_rows = products_by_id.get(product_id) or []
        if not regional_rows:
            continue

        any_discount = any(_is_discounted_product(product) for product in regional_rows)
        if not any_discount:
            continue

        seen_ids.add(product_id)

        # Choose representative product for name/url — pick the row with the deepest discount.
        regional_rows_sorted = sorted(
            regional_rows,
            key=lambda product: (_discount_percent(product) or 0),
            reverse=True,
        )
        representative = regional_rows_sorted[0]
        name = (representative.get_display_name() if hasattr(representative, "get_display_name") else None) or representative.name or product_id

        max_discount = max(((_discount_percent(product) or 0) for product in regional_rows), default=0)
        discount_text = f"(-{max_discount}%)" if max_discount else ""

        # Region rows in display order. Skip region if no price data for that region.
        region_blocks: list[dict] = []
        rows_by_region = {_region(product): product for product in regional_rows}
        for region_code in REGION_DISPLAY_ORDER:
            product = rows_by_region.get(region_code)
            if product is None:
                continue
            block = _region_price_block(product)
            if block is None:
                continue
            region_blocks.append(block)

        if not region_blocks:
            continue

        games.append(
            {
                "product_id": product_id,
                "name": name,
                "url": _product_url(product_id, _region(representative)),
                "discount_percent": max_discount or None,
                "discount_text": discount_text,
                "regions": region_blocks,
            }
        )
    return games


def _telegram_text(*, games: list[dict], total_count: int, favorites_url: str, discount_end_text: str | None) -> str:
    header = (
        f"🗣 <b><a href=\"{html.escape(favorites_url, quote=True)}\">"
        f"Подешевели {total_count} игр из Избранного</a></b>"
    )
    blocks: list[str] = [header, ""]
    for game in games:
        title_html = (
            f"• <a href=\"{html.escape(game['url'], quote=True)}\">"
            f"<b>{html.escape(game['name'])}</b></a>"
        )
        if game.get("discount_text"):
            title_html += f" {html.escape(game['discount_text'])}"
        blocks.append(title_html)
        for region in game["regions"]:
            rub_pieces: list[str] = []
            if region.get("current_rub_text"):
                rub_pieces.append(html.escape(region["current_rub_text"]))
            if region.get("old_rub_text"):
                rub_pieces.append(f"<s>{html.escape(region['old_rub_text'])}</s>")
            local_pieces: list[str] = [html.escape(region["current_local_text"])]
            if region.get("old_local_text"):
                local_pieces.append(f"<s>{html.escape(region['old_local_text'])}</s>")
            row = html.escape(region["flag"])
            if rub_pieces:
                row += " " + " ".join(rub_pieces) + " / " + " ".join(local_pieces)
            else:
                row += " " + " ".join(local_pieces)
            blocks.append(row)
        blocks.append("")
    if discount_end_text:
        blocks.append(f"🏁 {html.escape(discount_end_text)}")
        blocks.append("")
    blocks.append(
        f"·••• <a href=\"{html.escape(favorites_url, quote=True)}\">"
        f"Открыть моё ИЗБРАННОЕ</a> •••·"
    )
    return "\n".join(blocks)


def _trim_to_telegram_limit(games: list[dict], *, total_count: int, favorites_url: str, discount_end_text: str | None) -> tuple[str, int]:
    """Renders text and shrinks games list until it fits TG_TEXT_LIMIT."""
    truncated: list[dict] = list(games)
    text = _telegram_text(
        games=truncated,
        total_count=total_count,
        favorites_url=favorites_url,
        discount_end_text=discount_end_text,
    )
    while len(text) > TG_TEXT_LIMIT and len(truncated) > 1:
        truncated.pop()
        text = _telegram_text(
            games=truncated,
            total_count=total_count,
            favorites_url=favorites_url,
            discount_end_text=discount_end_text,
        )
    return text, len(truncated)


def _combined_signature(games: list[dict]) -> str:
    payload_parts: list[str] = []
    for game in games:
        regions_part = "|".join(
            f"{r['region']}:{r.get('current_local_text') or ''}/{r.get('old_local_text') or ''}/{r.get('discount_end') or ''}"
            for r in game.get("regions") or []
        )
        payload_parts.append(f"{game['product_id']}#{game.get('discount_percent') or 0}#{regions_part}")
    raw = "||".join(sorted(payload_parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def _ensure_notification_table(db: Session) -> None:
    FavoriteDiscountNotification.__table__.create(bind=db.get_bind(), checkfirst=True)


def _already_sent_combined(
    db: Session,
    *,
    user_id: int,
    signature: str,
    channel: str,
) -> bool:
    return bool(
        db.query(FavoriteDiscountNotification.id)
        .filter(
            FavoriteDiscountNotification.user_id == user_id,
            FavoriteDiscountNotification.product_id == COMBINED_BATCH_PRODUCT_ID,
            FavoriteDiscountNotification.discount_signature == signature,
            FavoriteDiscountNotification.channel == channel,
            FavoriteDiscountNotification.status == "sent",
        )
        .first()
    )


def _record_combined_notification(
    db: Session,
    *,
    user_id: int,
    signature: str,
    channel: str,
    recipient: str | None,
    status: str,
    error_message: str | None = None,
) -> None:
    db.add(
        FavoriteDiscountNotification(
            user_id=user_id,
            product_id=COMBINED_BATCH_PRODUCT_ID,
            region=None,
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


def _preferred_email(db: Session, user: User) -> str | None:
    return (
        _clean_email(getattr(user, "payment_email", None))
        or _latest_purchase_email(db, int(user.id))
        or _clean_email(getattr(user, "email", None))
    )


async def _send_telegram_combined(
    *,
    chat_id: int,
    text: str,
    banner_url: str | None,
) -> None:
    from aiogram import Bot
    from aiogram.types import LinkPreviewOptions

    link_preview = LinkPreviewOptions(
        is_disabled=False,
        url=banner_url or None,
        prefer_large_media=bool(banner_url),
        show_above_text=True,
    )

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            link_preview_options=link_preview,
        )
    finally:
        await bot.session.close()


async def _send_email_combined(email: str, payload: dict) -> None:
    await asyncio.to_thread(
        send_favorite_discount_combined_email,
        email=email,
        payload=payload,
    )


def _email_payload_from_games(games: list[dict], *, favorites_url: str, discount_end_text: str | None, total_count: int) -> dict:
    rendered_games = []
    for game in games:
        regions = []
        for region in game["regions"]:
            current_text = region["current_local_text"]
            current_rub = region.get("current_rub_text")
            full_current = current_text if not current_rub else f"{current_text} • {current_rub}"
            old_text = region.get("old_local_text")
            old_rub = region.get("old_rub_text")
            full_old = None
            if old_text and old_rub:
                full_old = f"{old_text} • {old_rub}"
            elif old_text:
                full_old = old_text
            regions.append(
                {
                    "flag": region["flag"],
                    "current": full_current,
                    "old": full_old,
                }
            )
        rendered_games.append(
            {
                "name": game["name"],
                "url": game["url"],
                "discount_text": game.get("discount_text"),
                "regions": regions,
            }
        )
    return {
        "games": rendered_games,
        "games_count": total_count,
        "favorites_url": favorites_url,
        "discount_end_text": discount_end_text,
    }


def _user_favorites_in_order(db: Session, user_id: int) -> list[UserFavoriteProduct]:
    return (
        db.query(UserFavoriteProduct)
        .filter(UserFavoriteProduct.user_id == user_id)
        .order_by(UserFavoriteProduct.created_at.desc(), UserFavoriteProduct.id.desc())
        .all()
    )


def _products_by_id(db: Session, product_ids: Sequence[str]) -> dict[str, list[Product]]:
    grouped: dict[str, list[Product]] = {}
    if not product_ids:
        return grouped
    sorted_ids = sorted({pid for pid in product_ids if pid})
    for chunk in _chunks(sorted_ids):
        rows = db.query(Product).filter(Product.id.in_(chunk)).all()
        for product in rows:
            if not product.id:
                continue
            grouped.setdefault(product.id, []).append(product)
    return grouped


async def _notify_user_combined(
    db: Session,
    *,
    user: User,
    games: list[dict],
    summary: FavoriteDiscountNotificationSummary,
    force_resend: bool = False,
) -> None:
    if not games:
        return

    favorites_url = _favorites_url()
    discount_end_text = _latest_discount_end(games)
    total_count = len(games)
    text, fitted_count = _trim_to_telegram_limit(
        games[:MAX_GAMES_PER_MESSAGE],
        total_count=total_count,
        favorites_url=favorites_url,
        discount_end_text=discount_end_text,
    )

    signature_games = games[:MAX_GAMES_PER_MESSAGE]
    signature = _combined_signature(signature_games)

    user_id = int(user.id)
    telegram_id = getattr(user, "telegram_id", None)
    email = _preferred_email(db, user)
    deliverable_channels = 0

    summary.candidates += 1

    if telegram_id and settings.TELEGRAM_BOT_TOKEN:
        deliverable_channels += 1
        if not force_resend and _already_sent_combined(db, user_id=user_id, signature=signature, channel="telegram"):
            summary.skipped_existing += 1
        else:
            try:
                await _send_telegram_combined(
                    chat_id=int(telegram_id),
                    text=text,
                    banner_url=_banner_url(),
                )
            except Exception as error:
                logger.exception(
                    "Failed to send combined Telegram favorite-discount notification user_id=%s",
                    user_id,
                )
                summary.failed += 1
                try:
                    _record_combined_notification(
                        db,
                        user_id=user_id,
                        signature=signature,
                        channel="telegram",
                        recipient=str(telegram_id),
                        status="failed",
                        error_message=f"{type(error).__name__}: {error}",
                    )
                except Exception:
                    logger.exception("Failed to record combined Telegram notification failure")
                    db.rollback()
            else:
                try:
                    _record_combined_notification(
                        db,
                        user_id=user_id,
                        signature=signature,
                        channel="telegram",
                        recipient=str(telegram_id),
                        status="sent",
                    )
                except Exception:
                    logger.exception("Failed to record combined Telegram notification success")
                    db.rollback()
                    summary.failed += 1
                else:
                    summary.sent += 1
                    summary.telegram_sent += 1

    if email and email_is_configured():
        deliverable_channels += 1
        if not force_resend and _already_sent_combined(db, user_id=user_id, signature=signature, channel="email"):
            summary.skipped_existing += 1
        else:
            email_payload = _email_payload_from_games(
                signature_games,
                favorites_url=favorites_url,
                discount_end_text=discount_end_text,
                total_count=total_count,
            )
            try:
                await _send_email_combined(email, email_payload)
            except Exception as error:
                logger.exception(
                    "Failed to send combined favorite-discount email user_id=%s",
                    user_id,
                )
                summary.failed += 1
                try:
                    _record_combined_notification(
                        db,
                        user_id=user_id,
                        signature=signature,
                        channel="email",
                        recipient=email,
                        status="failed",
                        error_message=f"{type(error).__name__}: {error}",
                    )
                except Exception:
                    logger.exception("Failed to record combined email notification failure")
                    db.rollback()
            else:
                try:
                    _record_combined_notification(
                        db,
                        user_id=user_id,
                        signature=signature,
                        channel="email",
                        recipient=email,
                        status="sent",
                    )
                except Exception:
                    logger.exception("Failed to record combined email notification success")
                    db.rollback()
                    summary.failed += 1
                else:
                    summary.sent += 1
                    summary.email_sent += 1

    # diagnostics: tweak fitted_count visibility
    if fitted_count != total_count:
        logger.info(
            "Combined favorite-discount: trimmed list for user_id=%s from %s to %s games (TG limit)",
            user_id,
            total_count,
            fitted_count,
        )

    if deliverable_channels == 0:
        summary.no_recipient += 1


async def notify_favorite_discounts_for_product_ids(
    db: Session,
    product_ids: Iterable[str] | None,
    *,
    force_resend: bool = False,
) -> dict[str, int]:
    """Send a single combined per-user message for all of their favorited & currently-discounted products.

    `product_ids` is the set of products that triggered the run (e.g. discount-update
    output). We use it only to decide which users to notify. Each notified user gets
    the FULL list of their currently-discounted favorites, sorted by the most recent
    additions to their favorites first.

    `force_resend=True` bypasses the duplicate-signature guard so admins can resend
    the current digest manually from the admin panel.
    """
    _ensure_notification_table(db)
    summary = FavoriteDiscountNotificationSummary()

    trigger_ids = {str(pid).strip() for pid in (product_ids or []) if str(pid).strip()}
    if not trigger_ids:
        return summary.to_dict()

    affected_user_ids = {
        row[0]
        for row in db.query(UserFavoriteProduct.user_id)
        .filter(UserFavoriteProduct.product_id.in_(list(trigger_ids)))
        .distinct()
        .all()
        if row[0]
    }
    if not affected_user_ids:
        return summary.to_dict()

    users = (
        db.query(User)
        .filter(User.id.in_(list(affected_user_ids)))
        .all()
    )
    if not users:
        return summary.to_dict()

    for user in users:
        favorites = _user_favorites_in_order(db, int(user.id))
        if not favorites:
            continue
        product_ids_for_user = [favorite.product_id for favorite in favorites if favorite.product_id]
        products_by_id = _products_by_id(db, product_ids_for_user)

        games = _build_user_games(
            favorites_in_order=favorites,
            products_by_id=products_by_id,
        )
        if not games:
            continue

        await _notify_user_combined(
            db,
            user=user,
            games=games,
            summary=summary,
            force_resend=force_resend,
        )

    return summary.to_dict()


async def notify_favorite_discounts_for_products(
    db: Session,
    products: Iterable[Product],
    *,
    force_resend: bool = False,
) -> dict[str, int]:
    """Compatibility shim for callers that pass Product objects (e.g. admin manual edits)."""
    product_ids = sorted({(product.id or "").strip() for product in products if product and product.id})
    return await notify_favorite_discounts_for_product_ids(
        db,
        product_ids,
        force_resend=force_resend,
    )


def notify_favorite_discounts_for_products_sync(
    db: Session,
    products: Iterable[Product],
    *,
    force_resend: bool = False,
) -> dict[str, int]:
    return asyncio.run(
        notify_favorite_discounts_for_products(
            db,
            products,
            force_resend=force_resend,
        )
    )


def notify_favorite_discounts_for_product_ids_sync(
    db: Session,
    product_ids: Iterable[str] | None,
    *,
    force_resend: bool = False,
) -> dict[str, int]:
    return asyncio.run(
        notify_favorite_discounts_for_product_ids(
            db,
            product_ids,
            force_resend=force_resend,
        )
    )
