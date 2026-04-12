import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import connection
from app.api.crud import FavoriteCRUD
from app.models import Product, User, UserFavoriteProduct


class SQLiteConnectionTests(unittest.TestCase):
    def test_select_sqlite_database_url_falls_back_when_source_is_not_writable(self):
        source_path = Path(tempfile.gettempdir()) / "game_bot2-source" / "products.db"
        fallback_path = Path(tempfile.gettempdir()) / "game_bot2-fallback" / "products.db"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.touch(exist_ok=True)

        with (
            patch.object(connection, "_sqlite_database_path", return_value=source_path),
            patch.object(connection, "_sqlite_fallback_candidates", return_value=[source_path, fallback_path]),
            patch.object(connection, "_path_is_writable", side_effect=lambda path: path == fallback_path),
            patch.object(connection, "_copy_sqlite_sidecars") as copy_sidecars,
        ):
            selected = connection._select_sqlite_database_url("sqlite:///./products.db")

        self.assertEqual(selected, connection._sqlite_url_for_path("sqlite:///./products.db", fallback_path))
        copy_sidecars.assert_called_once_with(source_path, fallback_path)

    def test_init_database_retries_with_fallback_on_readonly_sqlite(self):
        fallback_url = "sqlite:///fallback-products.db"
        current_engine = MagicMock()
        fallback_engine = MagicMock()
        call_sequence: list[str] = []

        def fake_create_tables():
            call_sequence.append(connection.DATABASE_URL)
            if len(call_sequence) == 1:
                raise OperationalError(
                    "CREATE TABLE site_auth_codes",
                    {},
                    Exception("attempt to write a readonly database"),
                )

        with (
            patch.object(connection, "RAW_DATABASE_URL", "sqlite:///./products.db"),
            patch.object(connection, "DATABASE_URL", "sqlite:///./products.db"),
            patch.object(connection, "engine", current_engine),
            patch.object(connection, "create_tables", side_effect=fake_create_tables),
            patch.object(connection, "_select_sqlite_database_url", return_value=fallback_url) as select_url,
            patch.object(connection, "_build_engine", return_value=fallback_engine) as build_engine,
            patch.object(connection, "sessionmaker", return_value="session-factory") as sessionmaker_mock,
        ):
            connection.init_database()
            final_database_url = connection.DATABASE_URL
            final_engine = connection.engine
            final_session_local = connection.SessionLocal

        self.assertEqual(call_sequence, ["sqlite:///./products.db", fallback_url])
        select_url.assert_called_once_with(
            "sqlite:///./products.db",
            excluded_urls={"sqlite:///./products.db"},
        )
        current_engine.dispose.assert_called_once()
        build_engine.assert_called_once_with(fallback_url)
        sessionmaker_mock.assert_called_once_with(autocommit=False, autoflush=False, bind=fallback_engine)
        self.assertEqual(final_database_url, fallback_url)
        self.assertIs(final_engine, fallback_engine)
        self.assertEqual(final_session_local, "session-factory")

    def test_migrate_user_favorite_products_table_rebuilds_foreign_key(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with engine.begin() as conn:
            Product.__table__.create(bind=conn, checkfirst=True)
            User.__table__.create(bind=conn, checkfirst=True)
            conn.execute(text("DROP TABLE IF EXISTS user_favorite_products"))
            conn.execute(
                text(
                    """
                    CREATE TABLE user_favorite_products (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        product_id VARCHAR(100) NOT NULL,
                        region VARCHAR(10),
                        created_at DATETIME NOT NULL,
                        UNIQUE (user_id, product_id),
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
                    )
                    """
                )
            )

        with SessionLocal() as db:
            user = User(
                email="fav@example.com",
                email_normalized="fav@example.com",
                telegram_id=777,
                preferred_region="TR",
                payment_email="fav@example.com",
                is_active=True,
                email_verified=True,
            )
            db.add(user)
            db.flush()

            product = Product(
                id="game-1",
                region="TR",
                name="Legacy Favorite Game",
                main_name="Legacy Favorite Game",
                price_try=100,
            )
            product2 = Product(
                id="game-2",
                region="TR",
                name="New Favorite Game",
                main_name="New Favorite Game",
                price_try=200,
            )
            db.add_all([product, product2])
            db.commit()

        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(
                text(
                    """
                    INSERT INTO user_favorite_products (user_id, product_id, region, created_at)
                    VALUES (:user_id, :product_id, :region, CURRENT_TIMESTAMP)
                    """
                ),
                {"user_id": 1, "product_id": "game-1", "region": "TR"},
            )
            conn.execute(text("PRAGMA foreign_keys=ON"))
            connection._migrate_user_favorite_products_table(conn)

        with engine.connect() as conn:
            fk_rows = conn.execute(text('PRAGMA foreign_key_list("user_favorite_products")')).mappings().all()

        self.assertEqual(len(fk_rows), 3)
        product_fk_rows = [row for row in fk_rows if row["table"] == "products"]
        self.assertEqual(len(product_fk_rows), 2)
        self.assertEqual([row["from"] for row in sorted(product_fk_rows, key=lambda row: row["seq"])], ["product_id", "region"])
        self.assertEqual([row["to"] for row in sorted(product_fk_rows, key=lambda row: row["seq"])], ["id", "region"])

        with SessionLocal() as db:
            inserted = FavoriteCRUD.add_to_favorites(db, 1, "game-2", "TR")
            self.assertIsNotNone(inserted)
            self.assertEqual(
                db.query(UserFavoriteProduct).filter(UserFavoriteProduct.product_id == "game-2").count(),
                1,
            )

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
