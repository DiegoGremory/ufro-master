"""
Crear índices e índices TTL para colecciones MongoDB
"""
from db.mongo import init_pymongo, get_db_name
from pymongo import ASCENDING, DESCENDING
from datetime import datetime


def ensure_indexes():
    """
    Crear todos los índices necesarios e índices TTL
    """
    db = init_pymongo()
    
    # Índices para colección traces
    traces_collection = db.traces
    traces_collection.create_index([("timestamp", DESCENDING)])
    traces_collection.create_index([("request_id", ASCENDING)], unique=True)
    traces_collection.create_index([("person_identified", ASCENDING), ("timestamp", DESCENDING)])
    traces_collection.create_index([("person_id", ASCENDING)])
    # Índice TTL: expira después de 90 días
    traces_collection.create_index([("created_at", ASCENDING)], expireAfterSeconds=7776000)
    
    # Índices para colección metrics
    metrics_collection = db.metrics
    metrics_collection.create_index([("timestamp", DESCENDING)])
    metrics_collection.create_index([("metric_name", ASCENDING), ("timestamp", DESCENDING)])
    metrics_collection.create_index([("metric_type", ASCENDING)])
    # Índice TTL: expira después de 30 días
    metrics_collection.create_index([("timestamp", ASCENDING)], expireAfterSeconds=2592000)
    
    # Índices para colección service_logs
    service_logs_collection = db.service_logs
    service_logs_collection.create_index([("timestamp", DESCENDING)])
    service_logs_collection.create_index([("service_name", ASCENDING), ("timestamp", DESCENDING)])
    service_logs_collection.create_index([("request_id", ASCENDING)])
    service_logs_collection.create_index([("endpoint", ASCENDING)])
    service_logs_collection.create_index([("status_code", ASCENDING)])
    service_logs_collection.create_index([("error", ASCENDING)])
    # Índice TTL: expira después de 60 días
    service_logs_collection.create_index([("created_at", ASCENDING)], expireAfterSeconds=5184000)
    
    # Índices para colección access_logs (H7)
    access_logs_collection = db.access_logs
    access_logs_collection.create_index([("ts", DESCENDING)])  # Recientes
    access_logs_collection.create_index([("user.type", ASCENDING), ("ts", DESCENDING)])  # Por tipo de usuario
    access_logs_collection.create_index([("route", ASCENDING), ("ts", DESCENDING)])  # Por ruta
    access_logs_collection.create_index([("decision", ASCENDING), ("ts", DESCENDING)])  # Por decisión
    access_logs_collection.create_index([("request_id", ASCENDING)], unique=True)  # ID único
    access_logs_collection.create_index([("status_code", ASCENDING)])  # Por código de estado
    # TTL opcional: si se guarda image_hash_ts, puede expirar en 7 días
    # access_logs_collection.create_index([("input.image_hash_ts", ASCENDING)], expireAfterSeconds=604800)
    
    print("Índices creados exitosamente")
    print(f"Base de datos: {get_db_name()}")
    print(f"Colecciones indexadas: traces, metrics, service_logs, access_logs")


if __name__ == "__main__":
    ensure_indexes()


