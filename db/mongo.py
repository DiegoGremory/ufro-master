"""
MongoDB connection using motor (async) or pymongo
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import Optional
import os


# Async client (motor)
motor_client: Optional[AsyncIOMotorClient] = None
motor_db = None


# Sync client (pymongo)
pymongo_client: Optional[MongoClient] = None
pymongo_db = None


def get_mongo_uri() -> str:
    """Get MongoDB URI from environment"""
    # Support both MONGODB_URI and MONGO_URI for compatibility
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        # Default with authentication if provided
        username = os.getenv("MONGO_USER", "admin")
        password = os.getenv("MONGO_PASSWORD", "admin123")
        host = os.getenv("MONGO_HOST", "localhost")
        port = os.getenv("MONGO_PORT", "27017")
        uri = f"mongodb://{username}:{password}@{host}:{port}"
    return uri


def get_db_name() -> str:
    """Get database name from environment"""
    return os.getenv("DB_NAME") or os.getenv("MONGODB_DB", "ufro")


async def init_motor():
    """Initialize async MongoDB client (motor)"""
    global motor_client, motor_db
    uri = get_mongo_uri()
    db_name = get_db_name()
    motor_client = AsyncIOMotorClient(uri)
    motor_db = motor_client[db_name]
    return motor_db


def init_pymongo():
    """Initialize sync MongoDB client (pymongo)"""
    global pymongo_client, pymongo_db
    uri = get_mongo_uri()
    db_name = get_db_name()
    pymongo_client = MongoClient(uri)
    pymongo_db = pymongo_client[db_name]
    return pymongo_db


async def close_motor():
    """Close async MongoDB client"""
    global motor_client
    if motor_client:
        motor_client.close()


def close_pymongo():
    """Close sync MongoDB client"""
    global pymongo_client
    if pymongo_client:
        pymongo_client.close()


