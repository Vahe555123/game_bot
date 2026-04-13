import hashlib
import hmac
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from app.auth.oauth_service import OAuthService, VK_ID_AUTHORIZE_URL
from app.auth.schemas import TelegramAuthRequest
from app.auth.security import verify_signed_oauth_state
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


class OAuthServiceVKTests(unittest.TestCase):
    def test_vk_authorization_url_uses_vk_id_pkce_flow(self):
        oauth_service = OAuthService(auth_service=FakeAuthService())

        with (
            patch.object(settings, "VK_CLIENT_ID", "vk-client-id"),
            patch.object(settings, "VK_CLIENT_SECRET", ""),
            patch.object(settings, "PUBLIC_APP_URL", "https://play-save.ru"),
            patch.object(settings, "AUTH_OAUTH_STATE_SECRET", "test-state-secret"),
        ):
            url = oauth_service.build_vk_authorization_url("/profile")

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        state = params["state"][0]
        state_payload = verify_signed_oauth_state(state, "test-state-secret")

        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}{parsed.path}", VK_ID_AUTHORIZE_URL)
        self.assertEqual(params["client_id"], ["vk-client-id"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertIn("code_challenge", params)
        self.assertEqual(state_payload["provider"], "vk")
        self.assertEqual(state_payload["next_path"], "/profile")
        self.assertTrue(state_payload["code_verifier"])


if __name__ == "__main__":
    unittest.main()
