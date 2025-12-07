"""
Conexión MongoDB usando motor (async) o pymongo
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import Optional
import os


# Cliente async (motor)
motor_client: Optional[AsyncIOMotorClient] = None
motor_db = None


# Cliente sync (pymongo)
pymongo_client: Optional[MongoClient] = None
pymongo_db = None


def get_mongo_uri() -> str:
    """Obtener URI de MongoDB desde variables de entorno"""
    # Soporta tanto MONGODB_URI como MONGO_URI para compatibilidad
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        # Por defecto con autenticación si se proporciona
        username = os.getenv("MONGO_USER", "admin")
        password = os.getenv("MONGO_PASSWORD", "admin123")
        host = os.getenv("MONGO_HOST", "localhost")
        port = os.getenv("MONGO_PORT", "27017")
        uri = f"mongodb://{username}:{password}@{host}:{port}"
    return uri


def get_db_name() -> str:
    """Obtener nombre de base de datos desde variables de entorno"""
    return os.getenv("DB_NAME") or os.getenv("MONGODB_DB", "ufro")


async def init_motor():
    """Inicializar cliente MongoDB async (motor)"""
    global motor_client, motor_db
    uri = get_mongo_uri()
    db_name = get_db_name()
    motor_client = AsyncIOMotorClient(uri)
    motor_db = motor_client[db_name]
    return motor_db


def init_pymongo():
    """Inicializar cliente MongoDB sync (pymongo)"""
    global pymongo_client, pymongo_db
    uri = get_mongo_uri()
    db_name = get_db_name()
    pymongo_client = MongoClient(uri)
    pymongo_db = pymongo_client[db_name]
    return pymongo_db


async def close_motor():
    """Cerrar cliente MongoDB async"""
    global motor_client
    if motor_client:
        motor_client.close()


def close_pymongo():
    """Cerrar cliente MongoDB sync"""
    global pymongo_client
    if pymongo_client:
        pymongo_client.close()


