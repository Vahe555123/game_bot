import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.exceptions import AuthServiceError
from app.auth.schemas import (
    RegisterRequest,
    SitePSNAccountUpdateRequest,
    SiteProfilePreferencesUpdateRequest,
)
from app.auth.security import hash_session_token
from app.auth.service import AuthService, seconds_until
from app.database.connection import Base
from app.models import PSNAccount, SiteAuthCode, SiteAuthSession, User
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


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.clock = FrozenClock(datetime(2026, 4, 4, 12, 0, 0))
        self.email_sender = EmailSenderSpy()
        self.service = AuthService(
            session_factory=self.SessionLocal,
            email_sender=self.email_sender,
            clock=self.clock,
        )

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

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

    def _create_verified_user(self):
        self.service.start_registration(self._register_payload())
        verification_code = self.email_sender.calls[-1][1]
        return self.service.verify_registration_code(email="user@test.com", code=verification_code)

    def _fetch_user(self, email: str) -> User | None:
        with self.SessionLocal() as db:
            return db.query(User).filter(User.email_normalized == email.lower()).first()

    def test_registration_verification_and_logout_use_sqlite(self):
        response = self.service.start_registration(self._register_payload())

        self.assertEqual(response.message, "Код подтверждения отправлен на email.")
        self.assertEqual(response.resend_available_in, settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)
        self.assertEqual(len(self.email_sender.calls), 1)
        self.assertEqual(self.email_sender.calls[0][0], "user@test.com")
        self.assertEqual(self.email_sender.calls[0][2], "register")

        with self.SessionLocal() as db:
            stored_user = db.query(User).filter(User.email_normalized == "user@test.com").one_or_none()
            self.assertIsNotNone(stored_user)
            self.assertFalse(stored_user.email_verified)
            self.assertTrue(stored_user.password_hash)
            self.assertEqual(stored_user.preferred_region, "TR")
            verification_doc = (
                db.query(SiteAuthCode)
                .filter(
                    SiteAuthCode.email_normalized == "user@test.com",
                    SiteAuthCode.purpose == "register",
                )
                .one_or_none()
            )
            self.assertIsNotNone(verification_doc)
            self.assertEqual(
                seconds_until(verification_doc.expires_at, now=self.clock()),
                settings.AUTH_EMAIL_CODE_TTL_MINUTES * 60,
            )

        verification_code = self.email_sender.calls[-1][1]
        user, session_token = self.service.verify_registration_code(
            email="user@test.com",
            code=verification_code,
            user_agent="pytest",
            ip_address="127.0.0.1",
        )

        self.assertTrue(user.email_verified)
        self.assertEqual(user.email, "user@test.com")
        self.assertTrue(session_token)

        with self.SessionLocal() as db:
            self.assertIsNone(
                db.query(SiteAuthCode)
                .filter(
                    SiteAuthCode.email_normalized == "user@test.com",
                    SiteAuthCode.purpose == "register",
                )
                .one_or_none()
            )
            self.assertIsNotNone(
                db.query(SiteAuthSession)
                .filter(SiteAuthSession.session_token_hash == hash_session_token(session_token))
                .one_or_none()
            )

        current_user = self.service.get_user_by_session_token(session_token)
        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.email, "user@test.com")

        self.service.logout(session_token)
        self.assertIsNone(self.service.get_user_by_session_token(session_token))

    def test_social_login_links_existing_user_by_email(self):
        self._create_verified_user()

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

        with self.SessionLocal() as db:
            stored_user = db.query(User).filter(User.email_normalized == "user@test.com").one()
            self.assertEqual(stored_user.google_id, "google-sub-1")
            self.assertIn("google", stored_user.auth_providers)

    def test_update_profile_preferences_and_psn_account_use_sqlite(self):
        user, _ = self._create_verified_user()

        updated_profile = self.service.update_profile_preferences(
            user.id,
            SiteProfilePreferencesUpdateRequest(
                preferred_region="IN",
                payment_email="checkout@test.com",
            ),
        )
        self.assertEqual(updated_profile.user.preferred_region, "IN")
        self.assertEqual(updated_profile.user.payment_email, "checkout@test.com")
        self.assertFalse(updated_profile.user.show_ukraine_prices)
        self.assertFalse(updated_profile.user.show_turkey_prices)
        self.assertTrue(updated_profile.user.show_india_prices)

        profile = self.service.update_psn_account(
            user.id,
            region="UA",
            payload=SitePSNAccountUpdateRequest(
                platform="PS5",
                psn_email="ua-psn@example.com",
                psn_password="ua-secret",
                backup_code="backup-code-1",
            ),
        )

        self.assertEqual(profile.psn_accounts["UA"].psn_email, "ua-psn@example.com")
        self.assertTrue(profile.psn_accounts["UA"].has_password)
        self.assertTrue(profile.psn_accounts["UA"].has_backup_code)

        with self.SessionLocal() as db:
            account = (
                db.query(PSNAccount)
                .filter(PSNAccount.user_id == int(user.id), PSNAccount.region == "UA")
                .one_or_none()
            )
            self.assertIsNotNone(account)
            self.assertEqual(account.psn_email, "ua-psn@example.com")
            self.assertTrue(account.has_credentials)


if __name__ == "__main__":
    unittest.main()
