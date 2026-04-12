import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.exceptions import AuthServiceError
from app.auth.service import build_public_user
from app.database.connection import Base
from app.models import User, UserFavoriteProduct
from app.site_admin.schemas import (
    AdminHelpContentUpdateRequest,
    AdminProductCreateRequest,
    AdminProductUpdateRequest,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
)
from app.site_admin.service import SiteAdminService


class SiteAdminServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

        self.service = SiteAdminService(
            session_factory=self.SessionLocal,
            now_provider=lambda: datetime(2026, 4, 5, 12, 0, 0),
        )

        admin_user = User(
            email="admin@example.com",
            email_normalized="admin@example.com",
            email_verified=True,
            username="admin",
            first_name="Site",
            last_name="Admin",
            telegram_id=1,
            preferred_region="TR",
            show_ukraine_prices=False,
            show_turkey_prices=True,
            show_india_prices=False,
            payment_email="admin@example.com",
            is_active=True,
            role="admin",
            created_at=datetime(2026, 4, 5, 12, 0, 0),
            updated_at=datetime(2026, 4, 5, 12, 0, 0),
        )
        self.db.add(admin_user)
        self.db.commit()
        self.db.refresh(admin_user)
        self.current_admin = build_public_user(admin_user)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_help_content_roundtrip_uses_sqlite(self):
        payload = AdminHelpContentUpdateRequest(
            eyebrow="Help",
            title="Support center",
            subtitle="All about payments and access",
            support_title="Need live help?",
            support_description="Managers can help with region, subscription, and order access.",
            support_button_label="Write to manager",
            support_button_url="https://t.me/support",
            purchases_title="Where purchases live",
            purchases_description="Orders are stored in SQLite now.",
            purchases_button_label="Open orders",
            purchases_button_url="https://oplata.info",
            social_links=[{"label": "Telegram", "url": "https://t.me/support"}],
            sections=[
                {"title": "First", "body": "Body one"},
                {"title": "Second", "body": "Body two"},
            ],
            faq_items=[
                {"question": "Q1", "answer": "A1"},
            ],
        )

        updated = self.service.update_help_content(payload)
        fetched = self.service.get_help_content()

        self.assertEqual(updated.title, "Support center")
        self.assertEqual(fetched.title, "Support center")
        self.assertEqual(fetched.social_links[0].label, "Telegram")
        self.assertIsNotNone(fetched.updated_at)

    def test_user_crud_roundtrip_uses_sqlite(self):
        created_user = self.service.create_user(
            AdminUserCreateRequest(
                email="new@example.com",
                password="secretpass123",
                email_verified=True,
                username="newbie",
                first_name="New",
                last_name="User",
                telegram_id=555,
                preferred_region="UA",
                payment_email="buy@example.com",
                platform="PS5",
                psn_email="psn@example.com",
                role="client",
                is_active=True,
            )
        )

        self.assertEqual(created_user.email, "new@example.com")
        self.assertEqual(created_user.telegram_id, 555)

        listed = self.service.list_users(self.db, page=1, limit=10, search="new@example.com")
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.users[0].email, "new@example.com")

        updated_user = self.service.update_user(
            created_user.id,
            AdminUserUpdateRequest(
                first_name="Updated",
                preferred_region="IN",
                payment_email="updated@example.com",
                role="client",
            ),
            current_admin=self.current_admin,
        )
        self.assertEqual(updated_user.first_name, "Updated")
        self.assertEqual(updated_user.preferred_region, "IN")
        self.assertEqual(updated_user.payment_email, "updated@example.com")

        with self.SessionLocal() as db:
            stored_user = db.query(User).filter(User.email_normalized == "new@example.com").one()
            self.assertEqual(stored_user.first_name, "Updated")
            self.assertEqual(stored_user.preferred_region, "IN")

        self.service.delete_user(created_user.id, current_admin=self.current_admin)
        with self.SessionLocal() as db:
            self.assertIsNone(db.query(User).filter(User.email_normalized == "new@example.com").first())

    def test_update_user_cannot_demote_current_admin(self):
        with self.assertRaises(AuthServiceError) as error_context:
            self.service.update_user(
                str(self.current_admin.id),
                AdminUserUpdateRequest(role="client"),
                current_admin=self.current_admin,
            )

        self.assertEqual(error_context.exception.status_code, 400)

    def test_delete_user_cannot_delete_current_admin(self):
        with self.assertRaises(AuthServiceError) as error_context:
            self.service.delete_user(str(self.current_admin.id), current_admin=self.current_admin)

        self.assertEqual(error_context.exception.status_code, 400)

    def test_product_crud_roundtrip(self):
        created_product = self.service.create_product(
            self.db,
            AdminProductCreateRequest(
                id="game-123",
                region="TR",
                name="Test Game Deluxe Edition",
                main_name="Test Game",
                category="games",
                price_try=1499,
                ps_plus=True,
                players_online=True,
            ),
        )

        self.assertEqual(created_product.id, "game-123")
        self.assertTrue(created_product.ps_plus)
        self.assertTrue(created_product.players_online)
        self.assertEqual(created_product.favorite_users_total, 0)

        updated_product = self.service.update_product(
            self.db,
            product_id="game-123",
            region="TR",
            payload=AdminProductUpdateRequest(
                name="Test Game Ultimate Edition",
                discount=25,
                price_try=1299,
                players_online=False,
            ),
        )

        self.assertEqual(updated_product.name, "Test Game Ultimate Edition")
        self.assertEqual(updated_product.discount, 25)
        self.assertFalse(updated_product.players_online)

        self.service.delete_product(self.db, product_id="game-123", region="TR")
        with self.assertRaises(AuthServiceError) as error_context:
            self.service.get_product(self.db, product_id="game-123", region="TR")

        self.assertEqual(error_context.exception.status_code, 404)

    def test_product_details_include_regions_and_favorites(self):
        self.service.create_product(
            self.db,
            AdminProductCreateRequest(
                id="game-details",
                region="TR",
                name="Detail Game TR",
                main_name="Detail Game",
                price_try=1499,
            ),
        )
        self.service.create_product(
            self.db,
            AdminProductCreateRequest(
                id="game-details",
                region="UA",
                name="Detail Game UA",
                main_name="Detail Game",
                price_uah=799,
                localization="full",
            ),
        )

        favorite_user = User(
            telegram_id=321654,
            username="favorite_user",
            first_name="Fav",
            last_name="User",
            preferred_region="UA",
            payment_email="favorite@example.com",
            is_active=True,
            email_verified=False,
            created_at=datetime(2026, 4, 5, 12, 0, 0),
            updated_at=datetime(2026, 4, 5, 12, 0, 0),
        )
        self.db.add(favorite_user)
        self.db.commit()
        self.db.refresh(favorite_user)

        favorite = UserFavoriteProduct(
            user_id=favorite_user.id,
            product_id="game-details",
            region="UA",
        )
        self.db.add(favorite)
        self.db.commit()

        detail = self.service.get_product(self.db, product_id="game-details", region="TR")

        self.assertEqual(detail.favorite_users_total, 1)
        self.assertEqual(len(detail.favorites), 1)
        self.assertEqual(detail.favorites[0].telegram_id, 321654)
        self.assertEqual(len(detail.regional_products), 2)
        self.assertEqual(detail.available_regions, ["TR", "UA"])
        self.assertEqual(detail.missing_regions, ["IN"])
        self.assertEqual(detail.favorites_by_region["UA"], 1)

        self.service.delete_product_favorite(self.db, product_id="game-details", favorite_id=detail.favorites[0].id)
        refreshed = self.service.get_product(self.db, product_id="game-details", region="TR")
        self.assertEqual(refreshed.favorite_users_total, 0)

        deleted_count = self.service.delete_product_group(self.db, product_id="game-details")
        self.assertEqual(deleted_count, 2)

        with self.assertRaises(AuthServiceError):
            self.service.get_product(self.db, product_id="game-details", region="TR")


if __name__ == "__main__":
    unittest.main()
