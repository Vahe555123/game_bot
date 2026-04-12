import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.crud import FavoriteCRUD, ProductCRUD
from app.api.schemas import PaginationParams, ProductFilter
from app.database.connection import Base
from app.models import Product, User, UserFavoriteProduct


class ProductResolutionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
        )

    def tearDown(self):
        self.engine.dispose()

    def test_normalize_search_text_strips_diacritics_and_yo(self):
        self.assertEqual(
            ProductCRUD._normalize_search_text("God of War Ragnar\u00f6k"),
            "god of war ragnarok",
        )
        self.assertEqual(
            ProductCRUD._normalize_search_text("\u0420\u0430\u0433\u043d\u0430\u0440\u0451\u043a\u2122"),
            "\u0440\u0430\u0433\u043d\u0430\u0440\u0435\u043a",
        )

    def test_get_products_grouped_by_name_prefers_full_localization(self):
        with self.SessionLocal() as db:
            db.add_all(
                [
                    Product(
                        id="game-1",
                        region="TR",
                        name="God of War Ragnarok",
                        main_name="God of War Ragnar\u00f6k",
                        search_names="God of War Ragnar\u00f6k,God of War Ragnarok",
                        localization="subtitles",
                        type="Game",
                        price_try=100,
                    ),
                    Product(
                        id="game-1",
                        region="UA",
                        name="God of War Ragnarok",
                        main_name="God of War Ragnar\u00f6k",
                        search_names="God of War Ragnar\u00f6k,God of War Ragnarok",
                        localization="full",
                        type="Game",
                        price_uah=200,
                    ),
                ]
            )
            db.commit()

            filters = ProductFilter(search="ragnarok")
            pagination = PaginationParams(page=1, limit=20)

            with patch.object(
                ProductCRUD,
                "prepare_product_with_prices",
                side_effect=lambda product, db=None: {
                    "id": product.id,
                    "region": product.region,
                    "localization": product.localization,
                    "name": product.name,
                },
            ):
                products, total = ProductCRUD.get_products_grouped_by_name(db, filters, pagination)

        self.assertEqual(total, 1)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["region"], "UA")
        self.assertEqual(products[0]["localization"], "full")

    def test_get_by_id_with_fallback_handles_missing_region(self):
        with self.SessionLocal() as db:
            db.add_all(
                [
                    Product(
                        id="EP3969-PPSA01769_00-0000000000000WOA",
                        region="TR",
                        name="HITMAN World of Assassination",
                        main_name="HITMAN World of Assassination",
                        search_names="HITMAN World of Assassination",
                        localization="none",
                        type="Game",
                        price_try=120,
                    ),
                    Product(
                        id="EP3969-PPSA01769_00-0000000000000WOA",
                        region="IN",
                        name="HITMAN World of Assassination",
                        main_name="HITMAN World of Assassination",
                        search_names="HITMAN World of Assassination",
                        localization="none",
                        type="Game",
                        price_inr=240,
                    ),
                ]
            )
            db.commit()

            strict = ProductCRUD.get_by_id(db, "EP3969-PPSA01769_00-0000000000000WOA", "UA")
            fallback = ProductCRUD.get_by_id_with_fallback(db, "EP3969-PPSA01769_00-0000000000000WOA", "UA")

        self.assertIsNone(strict)
        self.assertIsNotNone(fallback)
        self.assertIn(fallback.region, {"TR", "IN"})

    def test_add_to_favorites_canonicalizes_alias_id(self):
        with self.SessionLocal() as db:
            user = User(
                telegram_id=725505758,
                email="fav@example.com",
                email_normalized="fav@example.com",
                preferred_region="UA",
                payment_email="fav@example.com",
                show_ukraine_prices=True,
                show_turkey_prices=True,
                show_india_prices=True,
                email_verified=True,
                is_active=True,
            )
            product = Product(
                id="EP9000-PPSA08332_00-GOWRAGNAROK00000",
                region="UA",
                name="God of War Ragnarok",
                main_name="God of War Ragnar\u00f6k",
                search_names="God of War Ragnar\u00f6k,God of War Ragnarok,EP9000-PPSA08330_00-GOWRAGNAROK00000",
                localization="full",
                type="Game",
                price_uah=250,
            )
            db.add_all([user, product])
            db.commit()

            favorite = FavoriteCRUD.add_to_favorites(
                db,
                user.id,
                "EP9000-PPSA08330_00-GOWRAGNAROK00000",
                "UA",
            )
            stored_favorite_product_id = favorite.product_id if favorite else None
            stored_favorite_region = favorite.region if favorite else None

        self.assertIsNotNone(favorite)
        self.assertEqual(stored_favorite_product_id, "EP9000-PPSA08332_00-GOWRAGNAROK00000")
        self.assertEqual(stored_favorite_region, "UA")

        with self.SessionLocal() as db:
            self.assertTrue(FavoriteCRUD.is_favorite(db, user.id, "EP9000-PPSA08330_00-GOWRAGNAROK00000"))
            stored = db.query(UserFavoriteProduct).filter(UserFavoriteProduct.user_id == user.id).one()
            self.assertEqual(stored.product_id, "EP9000-PPSA08332_00-GOWRAGNAROK00000")
            self.assertEqual(stored.region, "UA")


if __name__ == "__main__":
    unittest.main()
