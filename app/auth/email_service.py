import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from config.settings import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the verification email could not be sent."""


def email_is_configured() -> bool:
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_PORT
        and settings.SMTP_USERNAME
        and settings.SMTP_APP_PASSWORD
        and settings.SMTP_FROM_EMAIL
    )


def send_verification_email(email: str, code: str) -> None:
    if not email_is_configured():
        raise EmailDeliveryError("SMTP не настроен. Укажите SMTP_USERNAME и SMTP_APP_PASSWORD.")

    message = EmailMessage()
    message["Subject"] = "Код подтверждения регистрации"
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(
        (
            "Ваш код подтверждения для PlayStation Store\n\n"
            f"Код: {code}\n"
            f"Срок действия: {settings.AUTH_EMAIL_CODE_TTL_MINUTES} минут\n\n"
            "Если вы не запрашивали этот код, просто проигнорируйте письмо."
        )
    )

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_APP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
                smtp.ehlo()
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_APP_PASSWORD)
                smtp.send_message(message)
    except Exception as error:
        logger.exception("Failed to send verification email to %s", email)
        raise EmailDeliveryError("Не удалось отправить письмо с кодом подтверждения.") from error
