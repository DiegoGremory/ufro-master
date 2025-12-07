"""
Aplicación FastAPI con endpoints:
- /identify-and-answer
- /metrics/*
- /healthz
"""
import os
import io
import time
import uuid
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime

from orchestrator.pp1_client import ask_pp1
from orchestrator.pp2_client import verify_person
from orchestrator.schemas import IdentifyResponse
from db.mongo import init_motor, close_motor
from db.queries import (
    save_trace,
    get_identification_rate,
    get_query_statistics,
    get_metric_aggregation
)

app = FastAPI(title="UFRO Orchestrator", version="1.0.0")

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables de entorno
THRESHOLD = float(os.getenv("THRESHOLD", "0.75"))
MARGIN = float(os.getenv("MARGIN", "0.1"))


@app.on_event("startup")
async def startup_event():
    """Inicializar conexión MongoDB al iniciar"""
    await init_motor()


@app.on_event("shutdown")
async def shutdown_event():
    """Cerrar conexión MongoDB al cerrar"""
    await close_motor()


@app.get("/healthz")
async def healthz():
    """Endpoint de health check"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/identify-and-answer", response_model=IdentifyResponse)
async def identify_and_answer(
    query: str = Form(..., description="Question about normative regulations"),
    image: UploadFile = File(..., description="Person image for verification (.jpg, .jpeg, .png)"),
    provider: Optional[str] = Form(None, description="LLM provider (deepseek or chatgpt)"),
    k: Optional[int] = Form(None, description="Top K results")
):
    """
    Identificar persona usando PP2 (verificación facial) y responder consulta usando PP1 (chatbot)
    
    Proceso:
    1. Verificar identidad de persona con PP2
    2. Si verificado arriba del umbral, preguntar a PP1
    3. Almacenar traza en MongoDB
    4. Retornar respuesta
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        # Leer contenido del archivo de imagen (resetear puntero)
        image.file.seek(0)
        image_content = image.file.read()
        
        # Crear objeto BytesIO para cliente PP2
        image_file = io.BytesIO(image_content)
        
        # Paso 1: Verificar persona con PP2
        pp2_result = await verify_person(
            image_file=image_file,
            filename=image.filename or "image.jpg",
            request_id=request_id
        )
        
        if not pp2_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"PP2 verification failed: {pp2_result.get('error')}"
            )
        
        person_identified = pp2_result.get("verified", False)
        confidence = pp2_result.get("confidence", 0.0)
        person_id = pp2_result.get("person_id")
        
        # Verificar si la confianza cumple el umbral
        if confidence < THRESHOLD:
            person_identified = False
        
        # Paso 2: Preguntar a PP1 (solo si la persona está identificada)
        pp1_result = None
        answer = ""
        
        if person_identified:
            pp1_result = await ask_pp1(
                message=query,
                provider=provider,
                k=k
            )
            
            if not pp1_result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail=f"Consulta PP1 falló: {pp1_result.get('error')}"
                )
            
            answer = pp1_result.get("answer", "No se pudo obtener una respuesta.")
        else:
            answer = f"Persona no identificada. Confianza: {confidence:.2f} (umbral requerido: {THRESHOLD:.2f})"
        
        # Calcular tiempo de procesamiento
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Paso 3: Almacenar traza en MongoDB
        trace_data = {
            "request_id": request_id,
            "query": query,
            "person_identified": person_identified,
            "confidence": confidence,
            "person_id": person_id,
            "answer": answer,
            "pp1_response": pp1_result or {},
            "pp2_response": pp2_result,
            "processing_time_ms": processing_time_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await save_trace(trace_data)
        
        # Paso 4: Retornar respuesta
        return IdentifyResponse(
            person_identified=person_identified,
            answer=answer,
            confidence=confidence,
            person_id=person_id,
            pp1_response=pp1_result,
            pp2_response=pp2_result,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Almacenar traza de error
        error_trace = {
            "request_id": request_id,
            "query": query,
            "person_identified": False,
            "confidence": 0.0,
            "answer": f"Error: {str(e)}",
            "pp1_response": {},
            "pp2_response": {},
            "processing_time_ms": (time.time() - start_time) * 1000,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
        await save_trace(error_trace)
        
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/metrics/identification-rate")
async def get_identification_rate_metric(time_range: str = "24h"):
    """Obtener métricas de tasa de éxito de identificación"""
    result = await get_identification_rate(time_range)
    return {
        "metric_name": "identification_rate",
        "time_range": time_range,
        "data": result,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics/query-statistics")
async def get_query_statistics_metric(time_range: str = "24h"):
    """Obtener métricas de estadísticas de consultas"""
    result = await get_query_statistics(time_range)
    return {
        "metric_name": "query_statistics",
        "time_range": time_range,
        "data": result,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics/{metric_name}")
async def get_metrics(metric_name: str, time_range: str = "24h"):
    """
    Obtener métricas por nombre
    
    Métricas disponibles:
    - identification-rate
    - query-statistics
    - métricas personalizadas almacenadas en MongoDB
    """
    if metric_name == "identification-rate":
        return await get_identification_rate_metric(time_range)
    elif metric_name == "query-statistics":
        return await get_query_statistics_metric(time_range)
    else:
        # Intentar obtener métrica personalizada
        result = await get_metric_aggregation(metric_name, time_range)
        return {
            "metric_name": metric_name,
            "time_range": time_range,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }


