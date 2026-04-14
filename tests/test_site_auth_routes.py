from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Response
from starlette.requests import Request

from app.api import site_auth_routes
from app.auth.exceptions import AuthServiceError
from config.settings import settings


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/oauth/vk/callback",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
        }
    )


class FakeOAuthService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def handle_vk_callback(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(session_token="vk-session-token", next_path="/profile")

    def handle_google_callback(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(session_token="google-session-token", next_path="/profile")


class FallbackOAuthService(FakeOAuthService):
    def handle_vk_callback(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["state"] == "bad-state":
            raise AuthServiceError(400, "OAuth state недействителен.")
        return SimpleNamespace(session_token="vk-session-token", next_path="/profile")


class SiteAuthRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def test_vk_callback_sets_cookie_on_redirect_response(self) -> None:
        fake_service = FakeOAuthService()

        with patch.object(site_auth_routes, "get_oauth_service", return_value=fake_service):
            response = await site_auth_routes.vk_oauth_callback(
                request=make_request(),
                response=Response(),
                code="vk-code",
                state=None,
                redirect_state="signed-state",
                device_id="vk-device-id",
                error=None,
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("auth_provider=vk", response.headers["location"])
        self.assertIn(f"{settings.AUTH_SESSION_COOKIE_NAME}=vk-session-token", response.headers["set-cookie"])
        self.assertEqual(fake_service.calls[0]["state"], "signed-state")
        self.assertEqual(fake_service.calls[0]["device_id"], "vk-device-id")

    async def test_vk_callback_prefers_redirect_state_when_both_are_returned(self) -> None:
        fake_service = FakeOAuthService()

        with patch.object(site_auth_routes, "get_oauth_service", return_value=fake_service):
            response = await site_auth_routes.vk_oauth_callback(
                request=make_request(),
                response=Response(),
                code="vk-code",
                state="vk-service-state",
                redirect_state="signed-state",
                device_id="vk-device-id",
                error=None,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(fake_service.calls[0]["state"], "signed-state")

    async def test_vk_callback_tries_state_after_invalid_redirect_state(self) -> None:
        fake_service = FallbackOAuthService()

        with patch.object(site_auth_routes, "get_oauth_service", return_value=fake_service):
            response = await site_auth_routes.vk_oauth_callback(
                request=make_request(),
                response=Response(),
                code="vk-code",
                state="signed-state",
                redirect_state="bad-state",
                device_id="vk-device-id",
                error=None,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual([call["state"] for call in fake_service.calls], ["bad-state", "signed-state"])

    async def test_google_callback_sets_cookie_on_redirect_response(self) -> None:
        fake_service = FakeOAuthService()

        with patch.object(site_auth_routes, "get_oauth_service", return_value=fake_service):
            response = await site_auth_routes.google_oauth_callback(
                request=make_request(),
                response=Response(),
                code="google-code",
                state="signed-state",
                error=None,
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("auth_provider=google", response.headers["location"])
        self.assertIn(f"{settings.AUTH_SESSION_COOKIE_NAME}=google-session-token", response.headers["set-cookie"])
        self.assertEqual(fake_service.calls[0]["state"], "signed-state")


if __name__ == "__main__":
    unittest.main()
