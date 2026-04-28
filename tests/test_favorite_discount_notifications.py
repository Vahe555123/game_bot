import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.models import FavoriteDiscountNotification, Product, User, UserFavoriteProduct
from app.notifications.favorite_discounts import notify_favorite_discounts_for_product_ids
from config.settings import settings


class FavoriteDiscountNotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _add_discounted_favorite(self):
        now = datetime(2026, 4, 23, 12, 0, 0)
        user = User(
            email="client@example.com",
            email_normalized="client@example.com",
            email_verified=True,
            telegram_id=987654,
            username="client",
            preferred_region="TR",
            show_turkey_prices=True,
            payment_email="payments@example.com",
            is_active=True,
            role="client",
            created_at=now,
            updated_at=now,
        )
        product = Product(
            id="sale-game",
            region="TR",
            name="Sale Game",
            main_name="Sale Game",
            category="games",
            price_try=499,
            old_price_try=999,
            discount=50,
            discount_percent=50,
            discount_end="2026-05-01",
        )
        self.db.add_all([user, product])
        self.db.commit()
        self.db.refresh(user)
        self.db.add(
            UserFavoriteProduct(
                user_id=user.id,
                product_id=product.id,
                region=product.region,
            )
        )
        self.db.commit()

    def test_sends_email_and_telegram_once_per_discount_signature(self):
        self._add_discounted_favorite()

        email_sender = AsyncMock()
        telegram_sender = AsyncMock()
        with (
            patch("app.notifications.favorite_discounts.email_is_configured", return_value=True),
            patch("app.notifications.favorite_discounts._send_email_combined", email_sender),
            patch("app.notifications.favorite_discounts._send_telegram_combined", telegram_sender),
            patch.object(settings, "TELEGRAM_BOT_TOKEN", "token"),
        ):
            first_summary = asyncio.run(
                notify_favorite_discounts_for_product_ids(self.db, ["sale-game"])
            )
            second_summary = asyncio.run(
                notify_favorite_discounts_for_product_ids(self.db, ["sale-game"])
            )

        self.assertEqual(first_summary["candidates"], 1)
        self.assertEqual(first_summary["sent"], 2)
        self.assertEqual(first_summary["email_sent"], 1)
        self.assertEqual(first_summary["telegram_sent"], 1)
        self.assertEqual(first_summary["failed"], 0)
        self.assertEqual(second_summary["sent"], 0)
        self.assertEqual(second_summary["skipped_existing"], 2)
        self.assertEqual(email_sender.await_count, 1)
        self.assertEqual(telegram_sender.await_count, 1)

        history = self.db.query(FavoriteDiscountNotification).all()
        self.assertEqual(len(history), 2)
        self.assertEqual({record.channel for record in history}, {"email", "telegram"})

    def test_force_resend_allows_manual_repeat_send(self):
        self._add_discounted_favorite()

        email_sender = AsyncMock()
        telegram_sender = AsyncMock()
        with (
            patch("app.notifications.favorite_discounts.email_is_configured", return_value=True),
            patch("app.notifications.favorite_discounts._send_email_combined", email_sender),
            patch("app.notifications.favorite_discounts._send_telegram_combined", telegram_sender),
            patch.object(settings, "TELEGRAM_BOT_TOKEN", "token"),
        ):
            asyncio.run(notify_favorite_discounts_for_product_ids(self.db, ["sale-game"]))
            resend_summary = asyncio.run(
                notify_favorite_discounts_for_product_ids(
                    self.db,
                    ["sale-game"],
                    force_resend=True,
                )
            )

        self.assertEqual(resend_summary["sent"], 2)
        self.assertEqual(resend_summary["email_sent"], 1)
        self.assertEqual(resend_summary["telegram_sent"], 1)
        self.assertEqual(resend_summary["skipped_existing"], 0)
        self.assertEqual(email_sender.await_count, 2)
        self.assertEqual(telegram_sender.await_count, 2)

        history = self.db.query(FavoriteDiscountNotification).all()
        self.assertEqual(len(history), 4)


if __name__ == "__main__":
    unittest.main()
