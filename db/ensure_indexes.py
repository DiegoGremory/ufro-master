"""
Create indexes and TTL indexes for MongoDB collections
"""
from db.mongo import init_pymongo, get_db_name
from pymongo import ASCENDING, DESCENDING
from datetime import datetime


def ensure_indexes():
    """
    Create all necessary indexes and TTL indexes
    """
    db = init_pymongo()
    
    # Indexes for traces collection
    traces_collection = db.traces
    traces_collection.create_index([("timestamp", DESCENDING)])
    traces_collection.create_index([("request_id", ASCENDING)], unique=True)
    traces_collection.create_index([("person_identified", ASCENDING), ("timestamp", DESCENDING)])
    traces_collection.create_index([("person_id", ASCENDING)])
    # TTL index: expires after 90 days
    traces_collection.create_index([("created_at", ASCENDING)], expireAfterSeconds=7776000)
    
    # Indexes for metrics collection
    metrics_collection = db.metrics
    metrics_collection.create_index([("timestamp", DESCENDING)])
    metrics_collection.create_index([("metric_name", ASCENDING), ("timestamp", DESCENDING)])
    metrics_collection.create_index([("metric_type", ASCENDING)])
    # TTL index: expires after 30 days
    metrics_collection.create_index([("timestamp", ASCENDING)], expireAfterSeconds=2592000)
    
    # Indexes for service_logs collection
    service_logs_collection = db.service_logs
    service_logs_collection.create_index([("timestamp", DESCENDING)])
    service_logs_collection.create_index([("service_name", ASCENDING), ("timestamp", DESCENDING)])
    service_logs_collection.create_index([("request_id", ASCENDING)])
    service_logs_collection.create_index([("endpoint", ASCENDING)])
    service_logs_collection.create_index([("status_code", ASCENDING)])
    service_logs_collection.create_index([("error", ASCENDING)])
    # TTL index: expires after 60 days
    service_logs_collection.create_index([("created_at", ASCENDING)], expireAfterSeconds=5184000)
    
    print("Indexes created successfully")
    print(f"Database: {get_db_name()}")
    print(f"Collections indexed: traces, metrics, service_logs")


if __name__ == "__main__":
    ensure_indexes()


