from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    }
    if "sqlite" in settings.DATABASE_URL
    else {},
)

if "sqlite" in settings.DATABASE_URL:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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

    if "sqlite" in settings.DATABASE_URL:
        with engine.begin() as connection:
            _migrate_users_table(connection)
            for statement in SQLITE_INDEX_STATEMENTS:
                connection.execute(text(statement))
            connection.execute(text("PRAGMA optimize"))

    print("Tables initialized")


def init_database():
    create_tables()
