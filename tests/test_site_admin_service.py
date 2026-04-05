import copy
import unittest
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.exceptions import AuthServiceError
from app.auth.schemas import SiteUserPublic
from app.database.connection import Base
from app.site_admin.schemas import (
    AdminProductCreateRequest,
    AdminProductUpdateRequest,
    AdminUserUpdateRequest,
)
from app.site_admin.service import SiteAdminService


class SimpleCollection:
    def __init__(self, documents=None):
        self.documents = copy.deepcopy(documents or [])

    def find_one(self, filter_query):
        for document in self.documents:
            if all(document.get(key) == value for key, value in filter_query.items()):
                return copy.deepcopy(document)
        return None

    def insert_one(self, document):
        stored = copy.deepcopy(document)
        if "_id" not in stored:
            stored["_id"] = f"user-{len(self.documents) + 1}"
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def update_one(self, filter_query, update):
        for index, document in enumerate(self.documents):
            if not all(document.get(key) == value for key, value in filter_query.items()):
                continue

            updated = copy.deepcopy(document)
            updated.update(copy.deepcopy(update.get("$set", {})))
            self.documents[index] = updated
            return SimpleNamespace(matched_count=1, modified_count=1)

        return SimpleNamespace(matched_count=0, modified_count=0)

    def delete_one(self, filter_query):
        for index, document in enumerate(self.documents):
            if not all(document.get(key) == value for key, value in filter_query.items()):
                continue
            self.documents.pop(index)
            return SimpleNamespace(deleted_count=1)

        return SimpleNamespace(deleted_count=0)

    def delete_many(self, filter_query):
        kept = []
        deleted_count = 0
        for document in self.documents:
            if all(document.get(key) == value for key, value in filter_query.items()):
                deleted_count += 1
            else:
                kept.append(document)
        self.documents = kept
        return SimpleNamespace(deleted_count=deleted_count)

    def count_documents(self, filter_query):
        if not filter_query:
            return len(self.documents)
        return sum(1 for document in self.documents if all(document.get(key) == value for key, value in filter_query.items()))


class SiteAdminServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.users = SimpleCollection(
            [
                {
                    "_id": "admin-1",
                    "email": "admin@example.com",
                    "email_normalized": "admin@example.com",
                    "email_verified": True,
                    "is_active": True,
                    "role": "admin",
                    "preferred_region": "TR",
                    "show_ukraine_prices": False,
                    "show_turkey_prices": True,
                    "show_india_prices": False,
                    "payment_email": "admin@example.com",
                    "psn_accounts": {},
                    "created_at": datetime(2026, 4, 5, 12, 0, 0),
                    "updated_at": datetime(2026, 4, 5, 12, 0, 0),
                }
            ]
        )
        self.codes = SimpleCollection()
        self.sessions = SimpleCollection()
        self.service = SiteAdminService(
            users=self.users,
            codes=self.codes,
            sessions=self.sessions,
            now_provider=lambda: datetime(2026, 4, 5, 12, 0, 0),
        )
        self.current_admin = SiteUserPublic(
            id="admin-1",
            email="admin@example.com",
            email_verified=True,
            username=None,
            first_name=None,
            last_name=None,
            telegram_id=None,
            preferred_region="TR",
            show_ukraine_prices=False,
            show_turkey_prices=True,
            show_india_prices=False,
            payment_email="admin@example.com",
            platform=None,
            psn_email=None,
            role="admin",
            is_admin=True,
            is_active=True,
            auth_providers=[],
            created_at=datetime(2026, 4, 5, 12, 0, 0),
            updated_at=datetime(2026, 4, 5, 12, 0, 0),
            last_login_at=None,
        )

    def tearDown(self):
        self.db.close()

    def test_update_user_cannot_demote_current_admin(self):
        with self.assertRaises(AuthServiceError) as error_context:
            self.service.update_user(
                "admin-1",
                AdminUserUpdateRequest(role="client"),
                current_admin=self.current_admin,
            )

        self.assertEqual(error_context.exception.status_code, 400)

    def test_delete_user_cannot_delete_current_admin(self):
        with self.assertRaises(AuthServiceError) as error_context:
            self.service.delete_user("admin-1", current_admin=self.current_admin)

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


if __name__ == "__main__":
    unittest.main()
