"""
Schemas Pydantic para validación de request/response
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class IdentifyRequest(BaseModel):
    """Schema de request para endpoint identify-and-answer"""
    query: str = Field(..., description="Pregunta sobre normativa")
    provider: Optional[str] = Field(None, description="Proveedor LLM (deepseek o chatgpt)")
    k: Optional[int] = Field(None, description="Top K resultados para recuperación")


class IdentifyResponse(BaseModel):
    """Schema de response para endpoint identify-and-answer"""
    person_identified: bool = Field(..., description="Si la persona fue identificada exitosamente")
    answer: str = Field(..., description="Respuesta del chatbot PP1")
    confidence: Optional[float] = Field(None, description="Score de confianza de verificación PP2")
    person_id: Optional[str] = Field(None, description="ID de persona identificada")
    pp1_response: Optional[Dict[str, Any]] = Field(None, description="Respuesta completa PP1")
    pp2_response: Optional[Dict[str, Any]] = Field(None, description="Respuesta completa PP2")
    timestamp: str = Field(..., description="Timestamp ISO de la request")


class MetricsResponse(BaseModel):
    """Schema de response para endpoint de métricas"""
    metric_name: str = Field(..., description="Nombre de la métrica")
    value: Any = Field(..., description="Valor de la métrica")
    timestamp: Optional[str] = Field(None, description="Timestamp de la métrica")
    aggregation: Optional[str] = Field(None, description="Tipo de agregación aplicada")


class TraceRequest(BaseModel):
    """Schema para almacenar trazas en MongoDB"""
    request_id: str
    query: str
    person_identified: bool
    confidence: Optional[float]
    answer: str
    pp1_response: Dict[str, Any]
    pp2_response: Dict[str, Any]
    processing_time_ms: float
    timestamp: str


class AnalyticsMetric(BaseModel):
    """Schema para métricas de analítica"""
    metric_type: str  # ej: "identification_rate", "avg_confidence", "query_count"
    value: Any
    time_range: str  # ej: "24h", "7d", "30d"
    timestamp: str


