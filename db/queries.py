"""
Queries de agregación MongoDB para endpoints /metrics/* y analítica
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from db.mongo import motor_db, init_motor
import uuid


async def save_trace(trace_data: Dict[str, Any]) -> str:
    """
    Guardar una traza en MongoDB
    
    Args:
        trace_data: Diccionario con datos de la traza
        
    Returns:
        ID de la traza
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
    Obtener tasa de éxito de identificación
    
    Args:
        time_range: Rango de tiempo (ej: "24h", "7d", "30d")
        
    Returns:
        Métricas de tasa de identificación
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
    Obtener estadísticas de consultas
    
    Args:
        time_range: Rango de tiempo
        
    Returns:
        Estadísticas de consultas
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
    Obtener datos agregados de métrica
    
    Args:
        metric_name: Nombre de la métrica
        time_range: Rango de tiempo (ej: "24h", "7d", "30d")
        
    Returns:
        Datos agregados de la métrica
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
    Obtener todas las métricas de una categoría
    
    Args:
        category: Categoría de métrica
        
    Returns:
        Lista de métricas
    """
    if not motor_db:
        await init_motor()
    
    cursor = motor_db.metrics.find({"category": category})
    return await cursor.to_list(length=None)


