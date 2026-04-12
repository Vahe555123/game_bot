from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return a naive UTC datetime for SQLite/SQLAlchemy defaults."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
