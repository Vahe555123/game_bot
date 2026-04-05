from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from config.settings import settings

from app.auth.email_service import EmailDeliveryError, email_is_configured

logger = logging.getLogger(__name__)


def _send_message(message: EmailMessage) -> None:
    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_APP_PASSWORD)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_APP_PASSWORD)
        smtp.send_message(message)


def _format_price_pair(local_price: float, currency_code: str, price_rub: float) -> str:
    return f"{local_price:.2f} {currency_code} • {price_rub:.2f} RUB"


def _build_shell(title: str, intro: str, body_html: str, button_url: str | None = None, button_text: str | None = None) -> str:
    action_html = ""
    if button_url and button_text:
        action_html = f"""
          <div class="email-action">
            <a href="{html.escape(button_url, quote=True)}" class="email-button">
              {html.escape(button_text)}
            </a>
          </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ru">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="dark">
    <meta name="supported-color-schemes" content="dark">
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: #07111f;
        color: #f8fbff;
        font-family: Manrope, Arial, sans-serif;
      }}

      .email-body {{
        margin: 0;
        padding: 32px 16px;
        background:
          radial-gradient(circle at top left, rgba(28, 181, 255, 0.16), transparent 36%),
          linear-gradient(180deg, #081120 0%, #050d18 100%);
      }}

      .email-shell {{
        max-width: 680px;
        margin: 0 auto;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 28px;
        overflow: hidden;
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(4, 10, 22, 0.99));
        box-shadow: 0 24px 64px rgba(0, 0, 0, 0.45);
      }}

      .email-hero {{
        padding: 32px;
        background:
          radial-gradient(circle at top left, rgba(38, 196, 255, 0.26), transparent 42%),
          linear-gradient(135deg, #10213b, #07111f 70%);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      }}

      .email-badge {{
        display: inline-block;
        padding: 8px 14px;
        border-radius: 999px;
        background: rgba(28, 181, 255, 0.16);
        color: #dff7ff;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
      }}

      .email-title {{
        margin: 18px 0 10px;
        font-size: 30px;
        line-height: 1.15;
        font-weight: 800;
      }}

      .email-intro {{
        margin: 0;
        font-size: 16px;
        line-height: 1.75;
        color: #cbd5e1;
      }}

      .email-content {{
        padding: 28px 32px 32px;
      }}

      .email-action {{
        margin-top: 24px;
      }}

      .email-button {{
        display: inline-block;
        padding: 14px 22px;
        border-radius: 999px;
        background: #1cb5ff;
        color: #ffffff !important;
        text-decoration: none;
        font-weight: 700;
      }}

      .email-detail-table {{
        width: 100%;
        border-collapse: collapse;
        border-radius: 22px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
      }}

      .email-detail-label,
      .email-detail-value {{
        padding: 14px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        vertical-align: top;
      }}

      .email-detail-row:last-child .email-detail-label,
      .email-detail-row:last-child .email-detail-value {{
        border-bottom: none;
      }}

      .email-detail-label {{
        width: 38%;
        color: #94a3b8;
        font-size: 13px;
      }}

      .email-detail-value {{
        color: #f8fbff;
        font-size: 14px;
        font-weight: 600;
      }}

      .email-card {{
        margin-top: 20px;
        padding: 18px 20px;
        border-radius: 22px;
        line-height: 1.75;
      }}

      .email-card-info {{
        background: rgba(28, 181, 255, 0.1);
        border: 1px solid rgba(28, 181, 255, 0.18);
        color: #dff7ff;
      }}

      .email-card-success {{
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.18);
        color: #ecfdf5;
      }}

      .email-card-title {{
        font-size: 20px;
        font-weight: 700;
      }}

      .email-card-text {{
        margin-top: 10px;
        white-space: pre-wrap;
      }}

      .email-items {{
        display: grid;
        gap: 12px;
        margin-top: 20px;
      }}

      .email-item {{
        padding: 14px 16px;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
      }}

      .email-item-label {{
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.12em;
      }}

      .email-item-value {{
        margin-top: 8px;
        font-size: 15px;
        line-height: 1.7;
        color: #f8fbff;
        font-weight: 600;
        white-space: pre-wrap;
      }}

      @media screen and (max-width: 640px) {{
        .email-body {{
          padding: 16px 10px !important;
        }}

        .email-shell {{
          border-radius: 22px !important;
        }}

        .email-hero {{
          padding: 24px 18px !important;
        }}

        .email-content {{
          padding: 20px 18px 22px !important;
        }}

        .email-title {{
          font-size: 24px !important;
        }}

        .email-intro {{
          font-size: 15px !important;
          line-height: 1.65 !important;
        }}

        .email-button {{
          display: block !important;
          width: 100% !important;
          box-sizing: border-box !important;
          text-align: center !important;
        }}

        .email-detail-row {{
          display: block !important;
        }}

        .email-detail-label,
        .email-detail-value {{
          display: block !important;
          width: auto !important;
          padding: 10px 14px !important;
        }}

        .email-detail-label {{
          border-bottom: none !important;
          padding-bottom: 0 !important;
        }}

        .email-detail-value {{
          padding-top: 6px !important;
          font-size: 15px !important;
        }}

        .email-card {{
          padding: 16px 14px !important;
        }}

        .email-card-title {{
          font-size: 18px !important;
        }}

        .email-item {{
          padding: 12px 14px !important;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="email-body">
      <div class="email-shell">
        <div class="email-hero">
          <div class="email-badge">PlayStation Store</div>
          <h1 class="email-title">{html.escape(title)}</h1>
          <p class="email-intro">{html.escape(intro)}</p>
        </div>
        <div class="email-content">
          {body_html}
          {action_html}
        </div>
      </div>
    </div>
  </body>
</html>
"""


def _details_table(rows: list[tuple[str, str]]) -> str:
    rendered_rows = []
    for label, value in rows:
        rendered_rows.append(
            f"""
            <tr class="email-detail-row">
              <td class="email-detail-label">{html.escape(label)}</td>
              <td class="email-detail-value">{html.escape(value)}</td>
            </tr>
            """
        )

    return f"""
      <table role="presentation" cellspacing="0" cellpadding="0" class="email-detail-table">
        {''.join(rendered_rows)}
      </table>
    """


def send_purchase_created_email(*, email: str, order_payload: dict) -> None:
    if not email_is_configured():
        raise EmailDeliveryError("SMTP РЅРµ РЅР°СЃС‚СЂРѕРµРЅ. РЈРєР°Р¶РёС‚Рµ SMTP_USERNAME Рё SMTP_APP_PASSWORD.")

    price_text = _format_price_pair(
        order_payload["local_price"],
        order_payload["currency_code"],
        order_payload["price_rub"],
    )

    rows = [
        ("РќРѕРјРµСЂ Р·Р°РєР°Р·Р°", order_payload["order_number"]),
        ("РўРѕРІР°СЂ", order_payload["product_name"]),
        ("Р РµРіРёРѕРЅ", order_payload["product_region"]),
        ("РЎС‚РѕРёРјРѕСЃС‚СЊ", price_text),
        ("Email РїРѕРєСѓРїРєРё", order_payload.get("payment_email") or "РќРµ СѓРєР°Р·Р°РЅ"),
        ("РЎС‚Р°С‚СѓСЃ", order_payload["status_label"]),
    ]

    body_html = (
        _details_table(rows)
        + """
        <div class="email-card email-card-info">
          <div class="email-card-text">
            После оплаты заказ появится в профиле. Если оплата уже выполнена, вернитесь на сайт и нажмите кнопку
            подтверждения оплаты, чтобы мы быстрее передали заказ в работу.
          </div>
        </div>
        """
    )

    message = EmailMessage()
    message["Subject"] = f'Р—Р°РєР°Р· {order_payload["order_number"]} СЃРѕР·РґР°РЅ'
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(
        f'Р—Р°РєР°Р· {order_payload["order_number"]} СЃРѕР·РґР°РЅ.\n'
        f'РўРѕРІР°СЂ: {order_payload["product_name"]}\n'
        f'Р РµРіРёРѕРЅ: {order_payload["product_region"]}\n'
        f'РЎС‚РѕРёРјРѕСЃС‚СЊ: {price_text}\n'
        f'РЎСЃС‹Р»РєР° РЅР° РѕРїР»Р°С‚Сѓ: {order_payload.get("payment_url") or "-"}'
    )
    message.add_alternative(
        _build_shell(
            "Р—Р°РєР°Р· СЃРѕР·РґР°РЅ",
            "РњС‹ РїРѕРґРіРѕС‚РѕРІРёР»Рё РґР»СЏ РІР°СЃ Р·Р°РєР°Р· Рё СЃРѕС…СЂР°РЅРёР»Рё РµРіРѕ РІ Р»РёС‡РЅРѕРј РєР°Р±РёРЅРµС‚Рµ.",
            body_html,
            button_url=order_payload.get("payment_url"),
            button_text="РџРµСЂРµР№С‚Рё Рє РѕРїР»Р°С‚Рµ",
        ),
        subtype="html",
    )

    try:
        _send_message(message)
    except Exception as error:
        logger.exception("Failed to send purchase created email to %s", email)
        raise EmailDeliveryError("РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ РїРёСЃСЊРјРѕ Рѕ СЃРѕР·РґР°РЅРёРё Р·Р°РєР°Р·Р°.") from error


def send_purchase_fulfilled_email(*, email: str, order_payload: dict) -> None:
    if not email_is_configured():
        raise EmailDeliveryError("SMTP РЅРµ РЅР°СЃС‚СЂРѕРµРЅ. РЈРєР°Р¶РёС‚Рµ SMTP_USERNAME Рё SMTP_APP_PASSWORD.")

    delivery = order_payload.get("delivery") or {}
    delivery_items = delivery.get("items") or []
    price_text = _format_price_pair(
        order_payload["local_price"],
        order_payload["currency_code"],
        order_payload["price_rub"],
    )

    rows = [
        ("РќРѕРјРµСЂ Р·Р°РєР°Р·Р°", order_payload["order_number"]),
        ("РўРѕРІР°СЂ", order_payload["product_name"]),
        ("Р РµРіРёРѕРЅ", order_payload["product_region"]),
        ("РЎС‚РѕРёРјРѕСЃС‚СЊ", price_text),
        ("Email РїРѕРєСѓРїРєРё", order_payload.get("payment_email") or "РќРµ СѓРєР°Р·Р°РЅ"),
        ("РЎС‚Р°С‚СѓСЃ", order_payload["status_label"]),
    ]

    if delivery_items:
        items_html = "".join(
            f"""
            <div class="email-item">
              <div class="email-item-label">{html.escape(item['label'])}</div>
              <div class="email-item-value">{html.escape(item['value'])}</div>
            </div>
            """
            for item in delivery_items
        )
        delivery_items_html = f'<div class="email-items">{items_html}</div>'
    else:
        delivery_items_html = ""

    delivery_message = delivery.get("message") or "Р”Р°РЅРЅС‹Рµ РїРѕ Р·Р°РєР°Р·Сѓ РіРѕС‚РѕРІС‹."

    body_html = (
        _details_table(rows)
        + f"""
        <div class="email-card email-card-success">
          <div class="email-card-title">{html.escape(delivery.get('title') or 'Р—Р°РєР°Р· РіРѕС‚РѕРІ')}</div>
          <div class="email-card-text">{html.escape(delivery_message)}</div>
        </div>
        {delivery_items_html}
        """
    )

    message = EmailMessage()
    message["Subject"] = f'Р—Р°РєР°Р· {order_payload["order_number"]} РіРѕС‚РѕРІ'
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(
        f'Р—Р°РєР°Р· {order_payload["order_number"]} РіРѕС‚РѕРІ.\n'
        f'РўРѕРІР°СЂ: {order_payload["product_name"]}\n'
        f'Р РµРіРёРѕРЅ: {order_payload["product_region"]}\n'
        f'РЎС‚РѕРёРјРѕСЃС‚СЊ: {price_text}\n'
        f'РЎРѕРѕР±С‰РµРЅРёРµ: {delivery_message}'
    )
    message.add_alternative(
        _build_shell(
            "Р—Р°РєР°Р· РіРѕС‚РѕРІ",
            "РќРёР¶Рµ РјС‹ РѕС‚РїСЂР°РІРёР»Рё РІСЃРµ РґР°РЅРЅС‹Рµ РїРѕ РІР°С€РµРјСѓ Р·Р°РєР°Р·Сѓ.",
            body_html,
            button_url=order_payload.get("manager_contact_url"),
            button_text="РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ РјРµРЅРµРґР¶РµСЂРѕРј" if order_payload.get("manager_contact_url") else None,
        ),
        subtype="html",
    )

    try:
        _send_message(message)
    except Exception as error:
        logger.exception("Failed to send purchase fulfilled email to %s", email)
        raise EmailDeliveryError("РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ РїРёСЃСЊРјРѕ СЃ РґР°РЅРЅС‹РјРё Р·Р°РєР°Р·Р°.") from error
