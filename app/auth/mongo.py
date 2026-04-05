import logging
from functools import lru_cache
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from config.settings import settings

logger = logging.getLogger(__name__)


OPTIONAL_IDENTITY_FIELDS = ("telegram_id", "google_id", "vk_id")


def _is_single_field_index(spec: dict[str, Any], field_name: str) -> bool:
    keys = spec.get("key") or []
    return len(keys) == 1 and keys[0][0] == field_name


def _is_optional_identity_index_compatible(spec: dict[str, Any]) -> bool:
    return bool(spec.get("unique")) and bool(spec.get("sparse"))


def ensure_optional_unique_identity_index(collection: Collection, field_name: str) -> None:
    index_info = collection.index_information()
    has_compatible_index = False

    for index_name, spec in list(index_info.items()):
        if index_name == "_id_":
            continue

        if not _is_single_field_index(spec, field_name):
            continue

        if _is_optional_identity_index_compatible(spec):
            has_compatible_index = True
            continue

        logger.warning(
            "Dropping legacy MongoDB index %s for %s because it is not unique+sparse",
            index_name,
            field_name,
        )
        collection.drop_index(index_name)

    if not has_compatible_index:
        collection.create_index([(field_name, ASCENDING)], unique=True, sparse=True)


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    return MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)


def get_mongo_database() -> Database:
    return get_mongo_client()[settings.MONGODB_DB_NAME]


def get_auth_users_collection() -> Collection:
    return get_mongo_database()[settings.MONGODB_AUTH_USERS_COLLECTION]


def get_auth_codes_collection() -> Collection:
    return get_mongo_database()[settings.MONGODB_AUTH_CODES_COLLECTION]


def get_auth_sessions_collection() -> Collection:
    return get_mongo_database()[settings.MONGODB_AUTH_SESSIONS_COLLECTION]


def init_mongo_indexes() -> bool:
    try:
        db = get_mongo_database()
        db.command("ping")

        users = get_auth_users_collection()
        codes = get_auth_codes_collection()
        sessions = get_auth_sessions_collection()

        for field_name in OPTIONAL_IDENTITY_FIELDS:
            users.update_many({field_name: None}, {"$unset": {field_name: ""}})
            users.update_many({field_name: ""}, {"$unset": {field_name: ""}})

        users.create_index([("email_normalized", ASCENDING)], unique=True, sparse=True)
        for field_name in OPTIONAL_IDENTITY_FIELDS:
            ensure_optional_unique_identity_index(users, field_name)
        users.create_index([("role", ASCENDING)])
        users.create_index([("is_active", ASCENDING)])

        codes.create_index([("email_normalized", ASCENDING), ("purpose", ASCENDING)], unique=True)
        codes.create_index("expires_at", expireAfterSeconds=0)

        sessions.create_index([("token_hash", ASCENDING)], unique=True)
        sessions.create_index([("user_id", ASCENDING)])
        sessions.create_index("expires_at", expireAfterSeconds=0)

        logger.info("✅ MongoDB auth indexes initialized")
        return True
    except PyMongoError as error:
        logger.warning("⚠️ MongoDB auth indexes were not initialized: %s", error)
        return False
