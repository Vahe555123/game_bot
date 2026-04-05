import logging
from functools import lru_cache

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from config.settings import settings

logger = logging.getLogger(__name__)


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

        users.update_many({"telegram_id": None}, {"$unset": {"telegram_id": ""}})
        users.update_many({"google_id": None}, {"$unset": {"google_id": ""}})
        users.update_many({"vk_id": None}, {"$unset": {"vk_id": ""}})

        users.create_index([("email_normalized", ASCENDING)], unique=True, sparse=True)
        users.create_index([("telegram_id", ASCENDING)], unique=True, sparse=True)
        users.create_index([("google_id", ASCENDING)], unique=True, sparse=True)
        users.create_index([("vk_id", ASCENDING)], unique=True, sparse=True)
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
