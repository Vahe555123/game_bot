import copy
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from bson import ObjectId

from app.auth.exceptions import AuthServiceError
from app.auth.schemas import (
    RegisterRequest,
    SitePSNAccountUpdateRequest,
    SiteProfilePreferencesUpdateRequest,
)
from app.auth.security import hash_session_token
from app.auth.service import AuthService, seconds_until
from config.settings import settings


class FrozenClock:
    def __init__(self, initial: datetime):
        self.current = initial

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> None:
        self.current += timedelta(**kwargs)


class EmailSenderSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, email: str, code: str, *, purpose: str = "register") -> None:
        self.calls.append((email, code, purpose))


class InMemoryCollection:
    def __init__(self):
        self.documents = []
        self._counter = 0

    def find_one(self, filter_query):
        for document in self.documents:
            if self._matches(document, filter_query):
                return copy.deepcopy(document)
        return None

    def insert_one(self, document):
        stored = copy.deepcopy(document)
        if "_id" not in stored:
            stored["_id"] = self._next_id()
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def update_one(self, filter_query, update):
        for index, document in enumerate(self.documents):
            if not self._matches(document, filter_query):
                continue

            updated = copy.deepcopy(document)
            for operator, changes in update.items():
                if operator != "$set":
                    raise NotImplementedError(f"Unsupported operator: {operator}")
                updated.update(copy.deepcopy(changes))

            self.documents[index] = updated
            return SimpleNamespace(matched_count=1, modified_count=1)

        return SimpleNamespace(matched_count=0, modified_count=0)

    def replace_one(self, filter_query, replacement, upsert=False):
        for index, document in enumerate(self.documents):
            if not self._matches(document, filter_query):
                continue

            updated = copy.deepcopy(replacement)
            updated["_id"] = document.get("_id", updated.get("_id", self._next_id()))
            self.documents[index] = updated
            return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

        if not upsert:
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

        created = copy.deepcopy(replacement)
        if "_id" not in created:
            created["_id"] = self._next_id()
        for key, value in filter_query.items():
            if isinstance(value, dict):
                continue
            created.setdefault(key, value)
        self.documents.append(created)
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=created["_id"])

    def delete_one(self, filter_query):
        for index, document in enumerate(self.documents):
            if not self._matches(document, filter_query):
                continue

            deleted = self.documents.pop(index)
            return SimpleNamespace(deleted_count=1, deleted_id=deleted.get("_id"))

        return SimpleNamespace(deleted_count=0, deleted_id=None)

    def _next_id(self):
        self._counter += 1
        return f"doc-{self._counter}"

    def _matches(self, document, filter_query):
        for key, expected in filter_query.items():
            actual = document.get(key)
            if isinstance(expected, dict):
                for operator, value in expected.items():
                    if operator == "$gt":
                        if actual is None or not actual > value:
                            return False
                    else:
                        raise NotImplementedError(f"Unsupported filter operator: {operator}")
                continue

            if actual != expected:
                return False
        return True


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.clock = FrozenClock(datetime(2026, 4, 4, 12, 0, 0))
        self.users = InMemoryCollection()
        self.codes = InMemoryCollection()
        self.sessions = InMemoryCollection()
        self.email_sender = EmailSenderSpy()
        self.service = AuthService(
            users=self.users,
            codes=self.codes,
            sessions=self.sessions,
            email_sender=self.email_sender,
            clock=self.clock,
        )

    def _register_payload(self):
        return RegisterRequest(
            email="User@Test.com",
            password="supersecret123",
            username="tester",
            first_name="Test",
            last_name="User",
            preferred_region="TR",
            payment_email="payments@test.com",
            platform="PS5",
            psn_email="psn@test.com",
        )

    def test_registration_creates_unverified_user_and_code(self):
        response = self.service.start_registration(self._register_payload())

        self.assertEqual(response.message, "Код подтверждения отправлен на email.")
        self.assertEqual(response.resend_available_in, settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)
        self.assertEqual(len(self.email_sender.calls), 1)
        self.assertEqual(self.email_sender.calls[0][0], "user@test.com")
        self.assertEqual(len(self.email_sender.calls[0][1]), settings.AUTH_EMAIL_CODE_LENGTH)
        self.assertEqual(self.email_sender.calls[0][2], "register")

        stored_user = self.users.find_one({"email_normalized": "user@test.com"})
        self.assertIsNotNone(stored_user)
        self.assertFalse(stored_user["email_verified"])
        self.assertNotEqual(stored_user["password_hash"], "supersecret123")
        self.assertEqual(stored_user["preferred_region"], "TR")
        self.assertEqual(stored_user["platform"], "PS5")
        self.assertNotIn("telegram_id", stored_user)

        verification_doc = self.codes.find_one(
            {"email_normalized": "user@test.com", "purpose": "register"}
        )
        self.assertIsNotNone(verification_doc)
        self.assertEqual(
            seconds_until(verification_doc["expires_at"], now=self.clock()),
            settings.AUTH_EMAIL_CODE_TTL_MINUTES * 60,
        )

    def test_resend_requires_cooldown_then_sends_new_code(self):
        self.service.start_registration(self._register_payload())

        with self.assertRaises(AuthServiceError) as error_context:
            self.service.resend_registration_code("user@test.com")

        self.assertEqual(error_context.exception.status_code, 429)
        self.assertGreater(error_context.exception.extra["resend_available_in"], 0)

        self.clock.advance(seconds=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)
        response = self.service.resend_registration_code("user@test.com")

        self.assertEqual(response.message, "Новый код подтверждения отправлен на email.")
        self.assertEqual(len(self.email_sender.calls), 2)

    def test_password_reset_flow_updates_password_and_logs_user_in(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]
        self.service.verify_registration_code(email="user@test.com", code=verification_code)

        response = self.service.start_password_reset("user@test.com")
        self.assertEqual(response.message, "Код для восстановления пароля отправлен на email.")
        self.assertEqual(self.email_sender.calls[-1][2], "password_reset")

        reset_code = self.email_sender.calls[-1][1]
        user, session_token = self.service.confirm_password_reset(
            email="user@test.com",
            code=reset_code,
            new_password="brandnewsecret123",
            user_agent="pytest-reset",
            ip_address="127.0.0.1",
        )

        self.assertEqual(user.email, "user@test.com")
        self.assertTrue(session_token)
        self.assertIsNotNone(
            self.sessions.find_one({"token_hash": hash_session_token(session_token)})
        )

        login_user, _ = self.service.login(email="user@test.com", password="brandnewsecret123")
        self.assertEqual(login_user.email, "user@test.com")

    def test_password_reset_resend_respects_cooldown(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]
        self.service.verify_registration_code(email="user@test.com", code=verification_code)
        self.service.start_password_reset("user@test.com")

        with self.assertRaises(AuthServiceError) as error_context:
            self.service.resend_password_reset_code("user@test.com")

        self.assertEqual(error_context.exception.status_code, 429)
        self.assertGreater(error_context.exception.extra["resend_available_in"], 0)

        self.clock.advance(seconds=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)
        response = self.service.resend_password_reset_code("user@test.com")

        self.assertEqual(response.message, "Новый код для восстановления пароля отправлен на email.")
        self.assertEqual(self.email_sender.calls[-1][2], "password_reset")

    def test_verify_confirms_email_and_creates_session(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]

        user, session_token = self.service.verify_registration_code(
            email="user@test.com",
            code=verification_code,
            user_agent="pytest",
            ip_address="127.0.0.1",
        )

        self.assertTrue(user.email_verified)
        self.assertEqual(user.email, "user@test.com")
        self.assertIsNotNone(
            self.sessions.find_one({"token_hash": hash_session_token(session_token)})
        )
        self.assertIsNone(
            self.codes.find_one({"email_normalized": "user@test.com", "purpose": "register"})
        )

        current_user = self.service.get_user_by_session_token(session_token)
        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.email, "user@test.com")

    def test_login_requires_verified_email_then_succeeds(self):
        self.service.start_registration(self._register_payload())

        with self.assertRaises(AuthServiceError) as error_context:
            self.service.login(email="user@test.com", password="supersecret123")

        self.assertEqual(error_context.exception.status_code, 403)

        verification_code = self.email_sender.calls[-1][1]
        self.service.verify_registration_code(email="user@test.com", code=verification_code)

        user, session_token = self.service.login(
            email="user@test.com",
            password="supersecret123",
            user_agent="pytest-login",
            ip_address="127.0.0.1",
        )

        self.assertEqual(user.email, "user@test.com")
        self.assertTrue(user.email_verified)
        self.assertTrue(session_token)

    def test_social_login_links_existing_user_by_email(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]
        self.service.verify_registration_code(email="user@test.com", code=verification_code)

        user, session_token = self.service.authenticate_social_user(
            provider="google",
            provider_id="google-sub-1",
            email="user@test.com",
            email_verified=True,
            first_name="Google",
            last_name="User",
        )

        self.assertEqual(user.email, "user@test.com")
        self.assertIn("google", user.auth_providers)
        self.assertTrue(session_token)

        stored_user = self.users.find_one({"email_normalized": "user@test.com"})
        self.assertEqual(stored_user["google_id"], "google-sub-1")

    def test_social_login_creates_telegram_user_without_email(self):
        user, session_token = self.service.authenticate_social_user(
            provider="telegram",
            provider_id="725505758",
            telegram_id=725505758,
            username="roma_nomak",
            first_name="Roma",
        )

        self.assertIsNone(user.email)
        self.assertEqual(user.telegram_id, 725505758)
        self.assertIn("telegram", user.auth_providers)
        self.assertTrue(session_token)

    def test_social_login_without_telegram_omits_null_telegram_id(self):
        user, session_token = self.service.authenticate_social_user(
            provider="google",
            provider_id="google-sub-2",
            email="google-only@test.com",
            email_verified=True,
            first_name="Google",
        )

        self.assertEqual(user.email, "google-only@test.com")
        self.assertTrue(session_token)

        stored_user = self.users.find_one({"email_normalized": "google-only@test.com"})
        self.assertIsNotNone(stored_user)
        self.assertNotIn("telegram_id", stored_user)

    def test_profile_preferences_switch_to_single_region_and_purchase_email(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]
        user, _ = self.service.verify_registration_code(email="user@test.com", code=verification_code)

        profile = self.service.update_profile_preferences(
            user.id,
            SiteProfilePreferencesUpdateRequest(
                preferred_region="UA",
                payment_email="checkout@test.com",
            ),
        )

        self.assertEqual(profile.user.preferred_region, "UA")
        self.assertTrue(profile.user.show_ukraine_prices)
        self.assertFalse(profile.user.show_turkey_prices)
        self.assertFalse(profile.user.show_india_prices)
        self.assertEqual(profile.user.payment_email, "checkout@test.com")

    def test_profile_psn_accounts_are_saved_per_region(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]
        user, _ = self.service.verify_registration_code(email="user@test.com", code=verification_code)

        profile = self.service.update_psn_account(
            user.id,
            region="UA",
            payload=SitePSNAccountUpdateRequest(
                platform="PS5",
                psn_email="ua-psn@test.com",
                psn_password="ua-pass",
                backup_code="ua-backup",
            ),
        )

        self.assertEqual(profile.psn_accounts["UA"].platform, "PS5")
        self.assertEqual(profile.psn_accounts["UA"].psn_email, "ua-psn@test.com")
        self.assertTrue(profile.psn_accounts["UA"].has_password)
        self.assertFalse(profile.psn_accounts["UA"].has_backup_code)
        self.assertFalse(profile.psn_accounts["TR"].has_password)

    def test_profile_methods_accept_object_id_as_public_string(self):
        object_id = ObjectId()
        self.users.insert_one(
            {
                "_id": object_id,
                "email": "objectid@test.com",
                "email_normalized": "objectid@test.com",
                "email_verified": True,
                "is_active": True,
                "preferred_region": "TR",
                "show_ukraine_prices": False,
                "show_turkey_prices": True,
                "show_india_prices": False,
                "payment_email": None,
                "psn_accounts": {},
                "created_at": self.clock(),
                "updated_at": self.clock(),
            }
        )

        profile = self.service.get_profile(str(object_id))
        self.assertEqual(profile.user.id, str(object_id))

        updated_profile = self.service.update_profile_preferences(
            str(object_id),
            SiteProfilePreferencesUpdateRequest(
                preferred_region="UA",
                payment_email="updated@test.com",
            ),
        )

        self.assertEqual(updated_profile.user.preferred_region, "UA")
        self.assertEqual(updated_profile.user.payment_email, "updated@test.com")


if __name__ == "__main__":
    unittest.main()
