import hashlib
import hmac
import time
import unittest
from unittest.mock import patch

from app.auth.oauth_service import OAuthService
from app.auth.schemas import TelegramAuthRequest
from config.settings import settings


def build_telegram_hash(payload: dict[str, object], bot_token: str) -> str:
    def stringify(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    data_check_string = "\n".join(
        f"{key}={stringify(value)}"
        for key, value in sorted(payload.items())
        if key != "hash" and value is not None
    )
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


class FakeAuthService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def authenticate_social_user(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "user-1"}, "session-token"


class OAuthServiceTelegramTests(unittest.TestCase):
    def test_accepts_allows_write_to_pm_in_hash_verification(self):
        fake_auth_service = FakeAuthService()
        oauth_service = OAuthService(auth_service=fake_auth_service)
        bot_token = "telegram-bot-token"

        raw_payload = {
            "id": 725505758,
            "first_name": "Roman",
            "username": "romanomak",
            "auth_date": int(time.time()),
            "allows_write_to_pm": True,
        }
        signed_payload = {
            **raw_payload,
            "hash": build_telegram_hash(raw_payload, bot_token),
        }

        with patch.object(settings, "TELEGRAM_BOT_TOKEN", bot_token):
            user, session_token = oauth_service.handle_telegram_login(
                payload=TelegramAuthRequest(**signed_payload),
                user_agent="pytest",
                ip_address="127.0.0.1",
            )

        self.assertEqual(user["id"], "user-1")
        self.assertEqual(session_token, "session-token")
        self.assertEqual(len(fake_auth_service.calls), 1)
        self.assertEqual(fake_auth_service.calls[0]["provider"], "telegram")
        self.assertEqual(fake_auth_service.calls[0]["telegram_id"], 725505758)

    def test_accepts_unknown_telegram_fields_in_hash_verification(self):
        fake_auth_service = FakeAuthService()
        oauth_service = OAuthService(auth_service=fake_auth_service)
        bot_token = "telegram-bot-token"

        raw_payload = {
            "id": 123456789,
            "first_name": "New",
            "last_name": "User",
            "auth_date": int(time.time()),
            "allows_write_to_pm": True,
            "language_code": "ru",
        }
        signed_payload = {
            **raw_payload,
            "hash": build_telegram_hash(raw_payload, bot_token),
        }

        with patch.object(settings, "TELEGRAM_BOT_TOKEN", bot_token):
            user, session_token = oauth_service.handle_telegram_login(
                payload=TelegramAuthRequest(**signed_payload),
                user_agent="pytest",
                ip_address="127.0.0.1",
            )

        self.assertEqual(user["id"], "user-1")
        self.assertEqual(session_token, "session-token")
        self.assertEqual(len(fake_auth_service.calls), 1)
        self.assertEqual(fake_auth_service.calls[0]["telegram_id"], 123456789)


if __name__ == "__main__":
    unittest.main()
