import hashlib
import hmac
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from app.auth.oauth_service import OAuthService, VK_ID_AUTHORIZE_URL, VK_ID_TOKEN_URL
from app.auth.schemas import TelegramAuthRequest
from app.auth.security import create_signed_oauth_state
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
            state_payload = oauth_service._parse_state(state, expected_provider="vk")


        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}{parsed.path}", VK_ID_AUTHORIZE_URL)
        self.assertEqual(params["client_id"], ["vk-client-id"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertIn("code_challenge", params)
        self.assertLessEqual(len(state), 240)
        self.assertEqual(state_payload["provider"], "vk")
        self.assertEqual(state_payload["next_path"], "/profile")
        self.assertGreaterEqual(len(state_payload["code_verifier"]), 43)

    def test_vk_authorization_url_falls_back_when_state_would_be_too_long(self):
        oauth_service = OAuthService(auth_service=FakeAuthService())

        with (
            patch.object(settings, "VK_CLIENT_ID", "vk-client-id"),
            patch.object(settings, "VK_CLIENT_SECRET", ""),
            patch.object(settings, "PUBLIC_APP_URL", "https://play-save.ru"),
            patch.object(settings, "AUTH_DEFAULT_REDIRECT_PATH", "/profile"),
            patch.object(settings, "AUTH_OAUTH_STATE_SECRET", "test-state-secret"),
        ):
            url = oauth_service.build_vk_authorization_url("/catalog?" + ("q=x&" * 120))
            params = parse_qs(urlparse(url).query)
            state = params["state"][0]
            state_payload = oauth_service._parse_state(state, expected_provider="vk")

        self.assertLessEqual(len(state), 240)
        self.assertEqual(state_payload["next_path"], "/profile")

    def test_vk_callback_falls_back_to_vk_id_user_info(self):
        fake_auth_service = FakeAuthService()
        oauth_service = OAuthService(auth_service=fake_auth_service)
        state = create_signed_oauth_state(
            {
                "provider": "vk",
                "next_path": "/profile",
                "code_verifier": "verifier-1",
                "iat": int(time.time()),
            },
            "test-state-secret",
        )

        class FakeResponse:
            def __init__(self, payload, status_code=200):
                self.payload = payload
                self.status_code = status_code

            def json(self):
                return self.payload

        class FakeClient:
            def __init__(self):
                self.post_calls = []
                self.get_calls = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url, **kwargs):
                self.post_calls.append((url, kwargs))
                if url != VK_ID_TOKEN_URL:
                    raise AssertionError(f"Unexpected token URL: {url}")
                return FakeResponse(
                    {
                        "access_token": "vk-access-token",
                        "user_id": 42,
                        "email": "vk@example.com",
                    }
                )

            def get(self, url, **kwargs):
                self.get_calls.append((url, kwargs))
                if len(self.get_calls) == 1:
                    return FakeResponse({"error": {"error_code": 5}})
                return FakeResponse(
                    {
                        "user": {
                            "user_id": 42,
                            "domain": "vk_user",
                            "first_name": "VK",
                            "last_name": "User",
                        }
                    }
                )

        fake_client = FakeClient()

        with (
            patch.object(settings, "VK_CLIENT_ID", "vk-client-id"),
            patch.object(settings, "VK_CLIENT_SECRET", ""),
            patch.object(settings, "AUTH_OAUTH_STATE_SECRET", "test-state-secret"),
            patch("app.auth.oauth_service.httpx.Client", return_value=fake_client),
        ):
            result = oauth_service.handle_vk_callback(
                code="vk-code",
                state=state,
                device_id="vk-device-id",
                user_agent="pytest",
                ip_address="127.0.0.1",
            )

        self.assertEqual(result.user["id"], "user-1")
        self.assertEqual(result.session_token, "session-token")
        self.assertEqual(fake_auth_service.calls[0]["provider"], "vk")
        self.assertEqual(fake_auth_service.calls[0]["provider_id"], "42")
        self.assertEqual(fake_auth_service.calls[0]["username"], "vk_user")
        self.assertEqual(len(fake_client.get_calls), 2)


if __name__ == "__main__":
    unittest.main()
