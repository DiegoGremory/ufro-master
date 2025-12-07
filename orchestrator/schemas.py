"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class IdentifyRequest(BaseModel):
    """Request schema for identify-and-answer endpoint"""
    query: str = Field(..., description="Question to ask about normative regulations")
    provider: Optional[str] = Field(None, description="LLM provider (deepseek or chatgpt)")
    k: Optional[int] = Field(None, description="Top K results for retrieval")


class IdentifyResponse(BaseModel):
    """Response schema for identify-and-answer endpoint"""
    person_identified: bool = Field(..., description="Whether person was successfully identified")
    answer: str = Field(..., description="Answer from PP1 chatbot")
    confidence: Optional[float] = Field(None, description="Confidence score from PP2 verification")
    person_id: Optional[str] = Field(None, description="Identified person ID")
    pp1_response: Optional[Dict[str, Any]] = Field(None, description="Full PP1 response")
    pp2_response: Optional[Dict[str, Any]] = Field(None, description="Full PP2 response")
    timestamp: str = Field(..., description="ISO timestamp of the request")


class MetricsResponse(BaseModel):
    """Response schema for metrics endpoint"""
    metric_name: str = Field(..., description="Name of the metric")
    value: Any = Field(..., description="Metric value")
    timestamp: Optional[str] = Field(None, description="Timestamp of the metric")
    aggregation: Optional[str] = Field(None, description="Type of aggregation applied")


class TraceRequest(BaseModel):
    """Schema for storing traces in MongoDB"""
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
    """Schema for analytics metrics"""
    metric_type: str  # e.g., "identification_rate", "avg_confidence", "query_count"
    value: Any
    time_range: str  # e.g., "24h", "7d", "30d"
    timestamp: str


