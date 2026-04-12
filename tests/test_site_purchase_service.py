import asyncio
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.exceptions import AuthServiceError
from app.database.connection import Base
from app.models import PSNAccount, Product, SitePurchaseOrder, User
from app.models.currency_rate import CurrencyRate
from app.site_orders.service import PaymentGenerationResult, SitePurchaseService


class StubPurchaseService(SitePurchaseService):
    async def _generate_payment(self, *, product, profile_context, current_price, price_rub):
        return PaymentGenerationResult(
            payment_url="https://example.com/pay",
            payment_provider="oplata",
            payment_type="topup",
            product_name=product.name or product.get_display_name(),
            platform=profile_context.platform,
            psn_email=profile_context.psn_email,
            price=current_price,
            price_rub=price_rub,
            currency=product.get_region_info()["code"],
            region=product.region,
            payment_metadata={"stub": True},
        )


class SitePurchaseServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

        self.service = StubPurchaseService(now_provider=lambda: datetime(2026, 4, 4, 12, 0, 0))

        self.db.add(
            CurrencyRate(
                currency_from="UAH",
                currency_to="RUB",
                price_min=0,
                price_max=None,
                rate=2.0,
                is_active=True,
            )
        )
        self.db.add(
            Product(
                id="game-1",
                region="UA",
                name="Far Cry 6 Deluxe Edition",
                main_name="Far Cry 6",
                platforms="PS4,PS5",
                image="https://example.com/image.jpg",
                price_uah=1000,
                ps_plus_price_uah=850,
            )
        )

        user = User(
            email="site@example.com",
            email_normalized="site@example.com",
            email_verified=True,
            payment_email="buy@example.com",
            platform="PS5",
            psn_email="ua-psn@example.com",
            preferred_region="UA",
            show_ukraine_prices=True,
            show_turkey_prices=False,
            show_india_prices=False,
            is_active=True,
            created_at=datetime(2026, 4, 4, 12, 0, 0),
            updated_at=datetime(2026, 4, 4, 12, 0, 0),
        )
        user.set_psn_password("psn-secret")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        account = PSNAccount(user_id=user.id, region="UA", psn_email="ua-psn@example.com", platform="PS5")
        account.set_psn_password("psn-secret")
        account.set_twofa_code("backup-code")
        self.db.add(account)
        self.db.commit()
        self.db.refresh(user)

        self.user = user

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_create_checkout_persists_order(self):
        order = asyncio.run(
            self.service.create_checkout(
                self.db,
                site_user_id=str(self.user.id),
                product_id="game-1",
                region="UA",
                use_ps_plus=True,
            )
        )

        self.assertEqual(order.status, "payment_pending")
        self.assertEqual(order.product_name, "Far Cry 6 Deluxe Edition")
        self.assertEqual(order.local_price, 850)
        self.assertEqual(order.price_rub, 1700)
        self.assertEqual(order.payment_email, "buy@example.com")
        self.assertEqual(order.psn_email, "ua-psn@example.com")

        orders = self.service.list_user_orders(self.db, site_user_id=str(self.user.id))
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_number, order.order_number)

        stored_order = self.db.query(SitePurchaseOrder).filter(SitePurchaseOrder.order_number == order.order_number).first()
        self.assertIsNotNone(stored_order)
        self.assertEqual(stored_order.site_user_id, str(self.user.id))
        self.assertEqual(stored_order.status, "payment_pending")

    def test_create_checkout_requires_payment_email(self):
        self.user.payment_email = ""
        self.db.add(self.user)
        self.db.commit()

        with self.assertRaises(AuthServiceError) as error_context:
            asyncio.run(
                self.service.create_checkout(
                    self.db,
                    site_user_id=str(self.user.id),
                    product_id="game-1",
                    region="UA",
                    use_ps_plus=False,
                )
            )

        self.assertEqual(error_context.exception.status_code, 400)
        self.assertIn("purchase_email", error_context.exception.extra["missing_fields"])

    def test_create_checkout_accepts_inline_checkout_overrides(self):
        self.user.payment_email = ""
        self.user.psn_email = ""
        self.user.psn_password_hash = None
        self.user.psn_password_salt = None
        self.db.add(self.user)
        self.db.commit()

        account = self.db.query(PSNAccount).filter(PSNAccount.user_id == self.user.id, PSNAccount.region == "UA").first()
        account.psn_email = ""
        account.set_psn_password(None)
        account.set_twofa_code(None)
        self.db.add(account)
        self.db.commit()

        order = asyncio.run(
            self.service.create_checkout(
                self.db,
                site_user_id=str(self.user.id),
                product_id="game-1",
                region="UA",
                use_ps_plus=False,
                purchase_email="override-buy@example.com",
                psn_email="override-psn@example.com",
                psn_password="override-pass",
                backup_code="override-backup",
            )
        )

        self.assertEqual(order.payment_email, "override-buy@example.com")
        self.assertEqual(order.psn_email, "override-psn@example.com")

    def test_list_user_orders_filters_by_days(self):
        recent_order = asyncio.run(
            self.service.create_checkout(
                self.db,
                site_user_id=str(self.user.id),
                product_id="game-1",
                region="UA",
                use_ps_plus=False,
            )
        )

        old_order = SitePurchaseOrder(
            order_number="PS-20260301-OLD123",
            site_user_id=str(self.user.id),
            user_email="site@example.com",
            user_display_name="site@example.com",
            product_id="game-1",
            product_region="UA",
            product_name="Far Cry 6 Deluxe Edition",
            product_image="https://example.com/image.jpg",
            product_platforms="PS4,PS5",
            currency_code="UAH",
            local_price=1000,
            price_rub=2000,
            use_ps_plus=False,
            payment_email="buy@example.com",
            psn_email="ua-psn@example.com",
            platform="PS5",
            payment_provider="oplata",
            payment_type="topup",
            payment_url="https://example.com/old-pay",
            status="payment_pending",
            created_at=datetime(2026, 3, 1, 12, 0, 0),
            updated_at=datetime(2026, 3, 1, 12, 0, 0),
        )
        self.db.add(old_order)
        self.db.commit()

        recent_orders = self.service.list_user_orders(self.db, site_user_id=str(self.user.id), days=7)
        self.assertEqual(len(recent_orders), 1)
        self.assertEqual(recent_orders[0].order_number, recent_order.order_number)

        all_orders = self.service.list_user_orders(self.db, site_user_id=str(self.user.id))
        self.assertEqual(len(all_orders), 2)

    def test_confirm_payment_moves_order_to_review(self):
        order = asyncio.run(
            self.service.create_checkout(
                self.db,
                site_user_id=str(self.user.id),
                product_id="game-1",
                region="UA",
                use_ps_plus=False,
            )
        )

        updated_order = self.service.confirm_payment(
            self.db,
            site_user_id=str(self.user.id),
            order_number=order.order_number,
        )

        self.assertEqual(updated_order.status, "payment_review")
        self.assertIsNotNone(updated_order.payment_submitted_at)


if __name__ == "__main__":
    unittest.main()
