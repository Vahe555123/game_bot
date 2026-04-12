import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from app.database import connection


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


if __name__ == "__main__":
    unittest.main()
