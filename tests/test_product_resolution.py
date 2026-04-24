import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.crud import FavoriteCRUD, ProductCRUD
from app.api.schemas import PaginationParams, ProductFilter
from app.database.connection import Base, _ensure_product_search_index, _normalize_search_text
from app.models import Product, User, UserFavoriteProduct
from config.settings import settings


class ProductResolutionTests(unittest.TestCase):
    def setUp(self):
        self._original_use_cards_table = settings.PRODUCTS_USE_CARDS_TABLE
        settings.PRODUCTS_USE_CARDS_TABLE = False
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
            dbapi_connection.create_function("normalize_search", 1, _normalize_search_text)

        Base.metadata.create_all(bind=self.engine)
        with self.engine.begin() as connection:
            _ensure_product_search_index(connection)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
        )

    def tearDown(self):
        settings.PRODUCTS_USE_CARDS_TABLE = self._original_use_cards_table
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

    def test_game_language_filter_uses_best_available_localization(self):
        with self.SessionLocal() as db:
            db.add_all(
                [
                    Product(
                        id="game-full",
                        region="TR",
                        name="Game Full",
                        main_name="Game Full",
                        search_names="Game Full",
                        localization="none",
                        type="Game",
                        price_try=100,
                    ),
                    Product(
                        id="game-full",
                        region="UA",
                        name="Game Full",
                        main_name="Game Full",
                        search_names="Game Full",
                        localization="full",
                        type="Game",
                        price_uah=200,
                    ),
                    Product(
                        id="game-partial",
                        region="TR",
                        name="Game Partial",
                        main_name="Game Partial",
                        search_names="Game Partial",
                        localization="subtitles",
                        type="Game",
                        price_try=120,
                    ),
                    Product(
                        id="game-none",
                        region="TR",
                        name="Game None",
                        main_name="Game None",
                        search_names="Game None",
                        localization="none",
                        type="Game",
                        price_try=140,
                    ),
                ]
            )
            db.commit()

            with patch.object(
                ProductCRUD,
                "prepare_product_with_multi_region_prices",
                side_effect=lambda product, *args, **kwargs: {
                    "id": product.id,
                    "region": product.region,
                    "localization": product.localization,
                    "main_name": product.main_name,
                },
            ):
                full_products, full_total = ProductCRUD.get_products_grouped_by_name(
                    db,
                    ProductFilter(game_language="full_ru"),
                    PaginationParams(page=1, limit=20),
                )
                partial_products, partial_total = ProductCRUD.get_products_grouped_by_name(
                    db,
                    ProductFilter(game_language="partial_ru"),
                    PaginationParams(page=1, limit=20),
                )
                none_products, none_total = ProductCRUD.get_products_grouped_by_name(
                    db,
                    ProductFilter(game_language="no_ru"),
                    PaginationParams(page=1, limit=20),
                )

        self.assertEqual(full_total, 1)
        self.assertEqual([product["id"] for product in full_products], ["game-full"])
        self.assertEqual(partial_total, 1)
        self.assertEqual([product["id"] for product in partial_products], ["game-partial"])
        self.assertEqual(none_total, 1)
        self.assertEqual([product["id"] for product in none_products], ["game-none"])

    def test_search_matches_title_fields_only(self):
        with self.SessionLocal() as db:
            db.add_all(
                [
                    Product(
                        id="god-of-war",
                        region="TR",
                        name="God of War",
                        main_name="God of War",
                        search_names="God of War",
                        localization="full",
                        type="Game",
                        price_try=100,
                    ),
                    Product(
                        id="false-positive",
                        region="TR",
                        name="Arslan: The Warriors of Legend",
                        main_name="Arslan: The Warriors of Legend",
                        search_names="Arslan: The Warriors of Legend",
                        description="A special God of War event inside the description.",
                        publisher="Another Studio",
                        localization="none",
                        type="Game",
                        price_try=120,
                    ),
                ]
            )
            db.commit()

            with patch.object(
                ProductCRUD,
                "prepare_product_with_multi_region_prices",
                side_effect=lambda product, *args, **kwargs: {
                    "id": product.id,
                    "region": product.region,
                    "main_name": product.main_name,
                },
            ):
                products, total = ProductCRUD.get_products_grouped_by_name(
                    db,
                    ProductFilter(search="God of War"),
                    PaginationParams(page=1, limit=20),
                )

        self.assertEqual(total, 1)
        self.assertEqual([product["id"] for product in products], ["god-of-war"])

    def test_get_products_grouped_by_name_supports_rating_sort(self):
        with self.SessionLocal() as db:
            db.add_all(
                [
                    Product(
                        id="game-top",
                        region="TR",
                        name="Top Game",
                        main_name="Top Game",
                        search_names="Top Game",
                        localization="full",
                        type="Game",
                        rating=4.9,
                        price_try=100,
                    ),
                    Product(
                        id="game-mid",
                        region="TR",
                        name="Mid Game",
                        main_name="Mid Game",
                        search_names="Mid Game",
                        localization="full",
                        type="Game",
                        rating=3.7,
                        price_try=120,
                    ),
                ]
            )
            db.commit()

            with patch.object(
                ProductCRUD,
                "prepare_product_with_multi_region_prices",
                side_effect=lambda product, *args, **kwargs: {
                    "id": product.id,
                    "rating": product.rating,
                },
            ):
                products, total = ProductCRUD.get_products_grouped_by_name(
                    db,
                    ProductFilter(sort="rating_desc"),
                    PaginationParams(page=1, limit=20),
                )

        self.assertEqual(total, 2)
        self.assertEqual([product["id"] for product in products], ["game-top", "game-mid"])

    def test_prepare_product_with_all_regions_marks_ps_plus_sale_as_discount(self):
        with self.SessionLocal() as db:
            product = Product(
                id="game-ps-plus-sale",
                region="TR",
                name="PS Plus Sale",
                main_name="PS Plus Sale",
                search_names="PS Plus Sale",
                localization="full",
                type="Game",
                price_try=100,
                old_price_try=100,
                ps_plus_price_try=80,
                release_date="2025-05-17",
            )
            db.add(product)
            db.commit()

            prepared = ProductCRUD.prepare_product_with_all_regions(product, db)

        tr_price = next(price for price in prepared["regional_prices"] if price["region"] == "TR")

        self.assertTrue(prepared["has_discount"])
        self.assertEqual(prepared["discount_percent"], 20)
        self.assertEqual(prepared["release_date"], "2025-05-17")
        self.assertTrue(tr_price["has_discount"])
        self.assertIsNone(tr_price["discount_percent"])
        self.assertEqual(tr_price["ps_plus_discount_percent"], 20)

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
