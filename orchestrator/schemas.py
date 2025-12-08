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


class Candidate(BaseModel):
    """Schema para candidato de identificación"""
    person_id: Optional[str] = Field(None, description="ID de persona")
    name: Optional[str] = Field(None, description="Nombre de la persona")
    score: float = Field(..., description="Score de confianza")
    service_count: Optional[int] = Field(None, description="Número de servicios que identificaron a esta persona")
    services: Optional[List[str]] = Field(None, description="Lista de servicios que identificaron a esta persona")


class Identity(BaseModel):
    """Schema para identidad principal"""
    name: Optional[str] = Field(None, description="Nombre de la persona identificada")
    person_id: Optional[str] = Field(None, description="ID de persona")
    score: float = Field(..., description="Score de confianza")


class Citation(BaseModel):
    """Schema para cita de documento"""
    doc: str = Field(..., description="Nombre del documento")
    page: str = Field(..., description="Número de página o 'N/A'")
    url: Optional[str] = Field(None, description="URL del documento (opcional)")


class NormativaAnswer(BaseModel):
    """Schema para respuesta normativa con citas"""
    text: str = Field(..., description="Texto de la respuesta")
    citations: List[Citation] = Field(default_factory=list, description="Lista de citas de documentos")


class IdentifyResponse(BaseModel):
    """Schema de response para endpoint identify-and-answer"""
    decision: str = Field(..., description="Decisión: identified | ambiguous | unknown")
    identity: Optional[Identity] = Field(None, description="Identidad principal si está identificada")
    candidates: List[Candidate] = Field(default_factory=list, description="Lista de candidatos ordenados por score")
    person_identified: bool = Field(..., description="Si la persona fue identificada exitosamente (compatibilidad)")
    answer: str = Field(..., description="Respuesta del chatbot PP1 (compatibilidad)")
    confidence: Optional[float] = Field(None, description="Score de confianza fusionado")
    person_id: Optional[str] = Field(None, description="ID de persona identificada (compatibilidad)")
    normativa_answer: Optional[NormativaAnswer] = Field(None, description="Respuesta normativa con citas (si hay query)")
    pp1_response: Optional[Dict[str, Any]] = Field(None, description="Respuesta completa PP1")
    pp2_response: Optional[Dict[str, Any]] = Field(None, description="Resultado de fusión PP2")
    timing_ms: Optional[float] = Field(None, description="Tiempo de procesamiento en milisegundos")
    request_id: Optional[str] = Field(None, description="ID de la request")
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


