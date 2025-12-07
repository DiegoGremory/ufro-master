"""
MongoDB aggregation queries for /metrics/* endpoints and analytics
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from db.mongo import motor_db, init_motor
import uuid


async def save_trace(trace_data: Dict[str, Any]) -> str:
    """
    Save a trace to MongoDB
    
    Args:
        trace_data: Trace data dictionary
        
    Returns:
        Trace ID
    """
    if not motor_db:
        await init_motor()
    
    trace_id = str(uuid.uuid4())
    trace_data["_id"] = trace_id
    trace_data["created_at"] = datetime.utcnow()
    
    await motor_db.traces.insert_one(trace_data)
    return trace_id


async def get_identification_rate(time_range: str = "24h") -> Dict[str, Any]:
    """
    Get identification success rate
    
    Args:
        time_range: Time range (e.g., "24h", "7d", "30d")
        
    Returns:
        Identification rate metrics
    """
    if not motor_db:
        await init_motor()
    
    time_deltas = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    
    delta = time_deltas.get(time_range, timedelta(hours=24))
    start_time = datetime.utcnow() - delta
    
    pipeline = [
        {
            "$match": {
                "timestamp": {"$gte": start_time.isoformat()}
            }
        },
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "identified": {
                    "$sum": {"$cond": [{"$eq": ["$person_identified", True]}, 1, 0]}
                },
                "avg_confidence": {
                    "$avg": "$confidence"
                },
                "min_confidence": {
                    "$min": "$confidence"
                },
                "max_confidence": {
                    "$max": "$confidence"
                }
            }
        },
        {
            "$project": {
                "total": 1,
                "identified": 1,
                "not_identified": {"$subtract": ["$total", "$identified"]},
                "identification_rate": {
                    "$cond": [
                        {"$eq": ["$total", 0]},
                        0,
                        {"$divide": ["$identified", "$total"]}
                    ]
                },
                "avg_confidence": 1,
                "min_confidence": 1,
                "max_confidence": 1
            }
        }
    ]
    
    result = await motor_db.traces.aggregate(pipeline).to_list(length=1)
    return result[0] if result else {
        "total": 0,
        "identified": 0,
        "not_identified": 0,
        "identification_rate": 0.0,
        "avg_confidence": 0.0
    }


async def get_query_statistics(time_range: str = "24h") -> Dict[str, Any]:
    """
    Get query statistics
    
    Args:
        time_range: Time range
        
    Returns:
        Query statistics
    """
    if not motor_db:
        await init_motor()
    
    time_deltas = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    
    delta = time_deltas.get(time_range, timedelta(hours=24))
    start_time = datetime.utcnow() - delta
    
    pipeline = [
        {
            "$match": {
                "timestamp": {"$gte": start_time.isoformat()}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_queries": {"$sum": 1},
                "avg_processing_time": {"$avg": "$processing_time_ms"},
                "min_processing_time": {"$min": "$processing_time_ms"},
                "max_processing_time": {"$max": "$processing_time_ms"}
            }
        }
    ]
    
    result = await motor_db.traces.aggregate(pipeline).to_list(length=1)
    return result[0] if result else {
        "total_queries": 0,
        "avg_processing_time": 0.0,
        "min_processing_time": 0.0,
        "max_processing_time": 0.0
    }


async def get_metric_aggregation(metric_name: str, time_range: str = "24h") -> Dict[str, Any]:
    """
    Get aggregated metric data
    
    Args:
        metric_name: Name of the metric
        time_range: Time range (e.g., "24h", "7d", "30d")
        
    Returns:
        Aggregated metric data
    """
    if not motor_db:
        await init_motor()
    
    time_deltas = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    
    delta = time_deltas.get(time_range, timedelta(hours=24))
    start_time = datetime.utcnow() - delta
    
    pipeline = [
        {
            "$match": {
                "metric_name": metric_name,
                "timestamp": {"$gte": start_time.isoformat()}
            }
        },
        {
            "$group": {
                "_id": None,
                "count": {"$sum": 1},
                "avg_value": {"$avg": "$value"},
                "min_value": {"$min": "$value"},
                "max_value": {"$max": "$value"}
            }
        }
    ]
    
    result = await motor_db.metrics.aggregate(pipeline).to_list(length=1)
    return result[0] if result else {}


async def get_metrics_by_category(category: str) -> List[Dict[str, Any]]:
    """
    Get all metrics in a category
    
    Args:
        category: Metric category
        
    Returns:
        List of metrics
    """
    if not motor_db:
        await init_motor()
    
    cursor = motor_db.metrics.find({"category": category})
    return await cursor.to_list(length=None)


