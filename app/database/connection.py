from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings

logger = logging.getLogger(__name__)


def _is_sqlite_url(database_url: str) -> bool:
    try:
        return make_url(database_url).drivername.startswith("sqlite")
    except Exception:
        return database_url.startswith("sqlite")


def _sqlite_database_path(database_url: str) -> Path | None:
    if not _is_sqlite_url(database_url):
        return None

    url = make_url(database_url)
    database = url.database
    if not database or database == ":memory:":
        return None

    path = Path(database).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    return path


def _sqlite_url_for_path(database_url: str, path: Path) -> str:
    url = make_url(database_url)
    return str(url.set(database=path.resolve(strict=False).as_posix()))


def _path_is_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    if path.exists() and not os.access(path, os.W_OK):
        return False

    return os.access(path.parent, os.W_OK | os.X_OK)


def _copy_sqlite_sidecars(source: Path, target: Path) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not prepare SQLite fallback directory %s: %s", target.parent, exc)
        return

    for suffix in ("", "-wal", "-shm", "-journal"):
        source_file = Path(f"{source}{suffix}")
        target_file = Path(f"{target}{suffix}")
        if not source_file.exists() or target_file.exists():
            continue
        try:
            shutil.copy2(source_file, target_file)
        except OSError as exc:
            logger.warning("Could not copy SQLite file %s to %s: %s", source_file, target_file, exc)


def _sqlite_fallback_candidates(database_url: str) -> list[Path]:
    source_path = _sqlite_database_path(database_url)
    if source_path is None:
        return []

    candidates: list[Path] = []
    seen: set[str] = set()

    def add_candidate(path: Path) -> None:
        resolved = str(path.resolve(strict=False))
        if resolved in seen:
            return
        seen.add(resolved)
        candidates.append(Path(resolved))

    add_candidate(source_path)

    fallback_root = Path(os.getenv("SQLITE_DATA_DIR", str(Path.home() / "data" / "game_bot2"))).expanduser()
    add_candidate(fallback_root / source_path.name)
    add_candidate(Path(tempfile.gettempdir()) / "game_bot2" / source_path.name)

    return candidates


def _select_sqlite_database_url(database_url: str, excluded_urls: set[str] | None = None) -> str:
    if not _is_sqlite_url(database_url):
        return database_url

    excluded_urls = excluded_urls or set()
    candidates = _sqlite_fallback_candidates(database_url)
    if not candidates:
        return database_url

    source_path = _sqlite_database_path(database_url)

    for candidate in candidates:
        candidate_url = _sqlite_url_for_path(database_url, candidate)
        if candidate_url in excluded_urls:
            continue

        if source_path is not None and candidate != source_path and source_path.exists() and not candidate.exists():
            _copy_sqlite_sidecars(source_path, candidate)

        if _path_is_writable(candidate):
            if candidate != source_path:
                logger.warning(
                    "SQLite database path %s is not writable, using fallback %s",
                    source_path,
                    candidate,
                )
            return candidate_url

    last_candidate = candidates[-1]
    last_candidate_url = _sqlite_url_for_path(database_url, last_candidate)
    if last_candidate_url not in excluded_urls:
        logger.warning(
            "No confirmed writable SQLite path found, using best-effort fallback %s",
            last_candidate,
        )
        return last_candidate_url

    return database_url


RAW_DATABASE_URL = settings.DATABASE_URL
DATABASE_URL = _select_sqlite_database_url(RAW_DATABASE_URL)


def _build_engine(database_url: str):
    connect_args = (
        {
            "check_same_thread": False,
            "timeout": 30,
        }
        if _is_sqlite_url(database_url)
        else {}
    )
    current_engine = create_engine(database_url, connect_args=connect_args)

    if _is_sqlite_url(database_url):

        @event.listens_for(current_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return current_engine


engine = _build_engine(DATABASE_URL)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SQLITE_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_products_region ON products(region)",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
    "CREATE INDEX IF NOT EXISTS idx_products_region_category ON products(region, category)",
    "CREATE INDEX IF NOT EXISTS idx_products_main_name ON products(main_name)",
    "CREATE INDEX IF NOT EXISTS idx_products_ps_plus_collection ON products(ps_plus_collection)",
    "CREATE INDEX IF NOT EXISTS idx_products_ea_access ON products(ea_access)",
    "CREATE INDEX IF NOT EXISTS idx_user_favorite_products_product_id ON user_favorite_products(product_id)",
)


def _sqlite_table_exists(connection, table_name: str) -> bool:
    result = connection.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :table_name"),
        {"table_name": table_name},
    ).first()
    return result is not None


def _sqlite_table_columns(connection, table_name: str) -> dict[str, dict]:
    rows = connection.execute(text(f'PRAGMA table_info("{table_name}")')).mappings().all()
    return {row["name"]: dict(row) for row in rows}


def _sqlite_foreign_key_groups(connection, table_name: str) -> list[list[dict]]:
    rows = connection.execute(text(f'PRAGMA foreign_key_list("{table_name}")')).mappings().all()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["id"], []).append(dict(row))
    return [sorted(group, key=lambda item: item["seq"]) for group in grouped.values()]


def _favorite_foreign_key_matches(group: list[dict]) -> bool:
    if len(group) != 2:
        return False

    if group[0].get("table") != "products" or group[1].get("table") != "products":
        return False

    from_columns = [row.get("from") for row in group]
    to_columns = [row.get("to") for row in group]
    return from_columns == ["product_id", "region"] and to_columns == ["id", "region"]


def _migrate_users_table(connection) -> None:
    from app.models.user import User

    if not _sqlite_table_exists(connection, "users"):
        return

    columns = _sqlite_table_columns(connection, "users")
    desired_columns = [
        "id",
        "telegram_id",
        "google_id",
        "vk_id",
        "email",
        "email_normalized",
        "email_verified",
        "password_hash",
        "username",
        "first_name",
        "last_name",
        "preferred_region",
        "show_ukraine_prices",
        "show_turkey_prices",
        "show_india_prices",
        "payment_email",
        "platform",
        "psn_email",
        "psn_password_hash",
        "psn_password_salt",
        "role",
        "auth_providers_json",
        "is_active",
        "created_at",
        "updated_at",
        "last_registration_at",
        "last_login_at",
        "registration_user_agent",
        "registration_ip_address",
        "login_user_agent",
        "login_ip_address",
    ]

    needs_rebuild = any(column not in columns for column in desired_columns)
    telegram_column = columns.get("telegram_id")
    if telegram_column and telegram_column.get("notnull"):
        needs_rebuild = True

    if not needs_rebuild:
        return

    connection.execute(text('ALTER TABLE "users" RENAME TO "users_legacy"'))
    User.__table__.create(bind=connection, checkfirst=True)

    legacy_columns = _sqlite_table_columns(connection, "users_legacy")

    def source_exists(name: str) -> bool:
        return name in legacy_columns

    def select_expr(column_name: str, default_sql: str) -> str:
        if source_exists(column_name):
            return f'"users_legacy"."{column_name}"'
        return default_sql

    select_columns = [
        ("id", select_expr("id", "NULL")),
        ("telegram_id", select_expr("telegram_id", "NULL")),
        ("google_id", select_expr("google_id", "NULL")),
        ("vk_id", select_expr("vk_id", "NULL")),
        ("email", select_expr("email", "NULL")),
        (
            "email_normalized",
            select_expr(
                "email_normalized",
                'LOWER("users_legacy"."email")' if source_exists("email") else "NULL",
            ),
        ),
        ("email_verified", select_expr("email_verified", "0")),
        ("password_hash", select_expr("password_hash", "NULL")),
        ("username", select_expr("username", "NULL")),
        ("first_name", select_expr("first_name", "NULL")),
        ("last_name", select_expr("last_name", "NULL")),
        ("preferred_region", select_expr("preferred_region", "'UA'")),
        ("show_ukraine_prices", select_expr("show_ukraine_prices", "0")),
        ("show_turkey_prices", select_expr("show_turkey_prices", "1")),
        ("show_india_prices", select_expr("show_india_prices", "0")),
        ("payment_email", select_expr("payment_email", "NULL")),
        ("platform", select_expr("platform", "NULL")),
        ("psn_email", select_expr("psn_email", "NULL")),
        ("psn_password_hash", select_expr("psn_password_hash", "NULL")),
        ("psn_password_salt", select_expr("psn_password_salt", "NULL")),
        ("role", select_expr("role", "'client'")),
        ("auth_providers_json", select_expr("auth_providers_json", "'[]'")),
        ("is_active", select_expr("is_active", "1")),
        ("created_at", select_expr("created_at", "CURRENT_TIMESTAMP")),
        ("updated_at", select_expr("updated_at", "CURRENT_TIMESTAMP")),
        ("last_registration_at", select_expr("last_registration_at", "NULL")),
        ("last_login_at", select_expr("last_login_at", "NULL")),
        ("registration_user_agent", select_expr("registration_user_agent", "NULL")),
        ("registration_ip_address", select_expr("registration_ip_address", "NULL")),
        ("login_user_agent", select_expr("login_user_agent", "NULL")),
        ("login_ip_address", select_expr("login_ip_address", "NULL")),
    ]

    insert_columns = ", ".join(f'"{column_name}"' for column_name, _ in select_columns)
    select_list = ", ".join(expr for _, expr in select_columns)
    connection.execute(text(f'INSERT INTO "users" ({insert_columns}) SELECT {select_list} FROM "users_legacy"'))
    connection.execute(text('DROP TABLE "users_legacy"'))


def _migrate_user_favorite_products_table(connection) -> None:
    from app.models.favorite import UserFavoriteProduct

    if not _sqlite_table_exists(connection, "user_favorite_products"):
        return

    columns = _sqlite_table_columns(connection, "user_favorite_products")
    desired_columns = [
        "id",
        "user_id",
        "product_id",
        "region",
        "created_at",
    ]

    foreign_key_groups = _sqlite_foreign_key_groups(connection, "user_favorite_products")
    has_expected_foreign_key = any(_favorite_foreign_key_matches(group) for group in foreign_key_groups)
    needs_rebuild = any(column not in columns for column in desired_columns) or not has_expected_foreign_key

    if not needs_rebuild:
        return

    connection.execute(text('ALTER TABLE "user_favorite_products" RENAME TO "user_favorite_products_legacy"'))
    UserFavoriteProduct.__table__.create(bind=connection, checkfirst=True)

    legacy_rows = connection.execute(
        text(
            'SELECT "id", "user_id", "product_id", "region", "created_at" '
            'FROM "user_favorite_products_legacy"'
        )
    ).mappings().all()

    normalized_rows: list[dict[str, object]] = []
    for legacy_row in legacy_rows:
        product_id = legacy_row.get("product_id")
        if not product_id:
            logger.warning("Skipping legacy favorite without product_id: %s", legacy_row)
            continue

        legacy_region = legacy_row.get("region")
        resolved_region = None
        if legacy_region:
            region_exists = connection.execute(
                text(
                    'SELECT 1 FROM "products" '
                    'WHERE "id" = :product_id AND "region" = :region '
                    'LIMIT 1'
                ),
                {"product_id": product_id, "region": legacy_region},
            ).first()
            if region_exists is not None:
                resolved_region = str(legacy_region).strip().upper() or None

        if resolved_region is None:
            resolved_region = connection.execute(
                text(
                    'SELECT "region" FROM "products" '
                    'WHERE "id" = :product_id '
                    'ORDER BY CASE "region" '
                    "WHEN 'TR' THEN 0 "
                    "WHEN 'IN' THEN 1 "
                    "WHEN 'UA' THEN 2 "
                    "ELSE 99 END, "
                    '"region" '
                    'LIMIT 1'
                ),
                {"product_id": product_id},
            ).scalar()
            if resolved_region is not None:
                resolved_region = str(resolved_region).strip().upper() or None

        if resolved_region is None:
            logger.warning(
                "Skipping legacy favorite %s because product %s is missing in products table",
                legacy_row.get("id"),
                product_id,
            )
            continue

        normalized_rows.append(
            {
                "id": legacy_row.get("id"),
                "user_id": legacy_row.get("user_id"),
                "product_id": product_id,
                "region": resolved_region,
                "created_at": legacy_row.get("created_at"),
            }
        )

    if normalized_rows:
        connection.execute(
            text(
                'INSERT INTO "user_favorite_products" ("id", "user_id", "product_id", "region", "created_at") '
                'VALUES (:id, :user_id, :product_id, :region, :created_at)'
            ),
            normalized_rows,
        )
    connection.execute(text('DROP TABLE "user_favorite_products_legacy"'))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    @contextmanager
    def session_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return session_context()


def create_tables():
    from app.models import (
        CurrencyRate,
        Localization,
        PSNAccount,
        Product,
        SiteAuthCode,
        SiteAuthSession,
        SiteContent,
        SitePurchaseOrder,
        User,
        UserFavoriteProduct,
    )

    _ = (
        CurrencyRate,
        Localization,
        PSNAccount,
        Product,
        SiteAuthCode,
        SiteAuthSession,
        SiteContent,
        SitePurchaseOrder,
        User,
        UserFavoriteProduct,
    )

    Base.metadata.create_all(bind=engine)

    if _is_sqlite_url(RAW_DATABASE_URL):
        with engine.begin() as connection:
            _migrate_users_table(connection)
            _migrate_user_favorite_products_table(connection)
            for statement in SQLITE_INDEX_STATEMENTS:
                connection.execute(text(statement))
            connection.execute(text("PRAGMA optimize"))

    print("Tables initialized")


def init_database():
    global DATABASE_URL, SessionLocal, engine

    readonly_error: OperationalError | None = None
    try:
        create_tables()
        return
    except OperationalError as exc:
        if "readonly database" not in str(exc).lower() or not _is_sqlite_url(RAW_DATABASE_URL):
            raise
        readonly_error = exc

    fallback_url = _select_sqlite_database_url(RAW_DATABASE_URL, excluded_urls={DATABASE_URL})
    if fallback_url == DATABASE_URL:
        if readonly_error is not None:
            raise readonly_error
        raise RuntimeError("SQLite database is not writable and no fallback path is available")

    logger.warning("Rebuilding SQLite engine with fallback database URL: %s", fallback_url)
    engine.dispose()
    DATABASE_URL = fallback_url
    engine = _build_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    create_tables()
