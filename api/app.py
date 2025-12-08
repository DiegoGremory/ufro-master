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
import hashlib
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime

from orchestrator.pp1_client import ask_pp1
from orchestrator.pp2_client import verify_all_services
from orchestrator.registry_loader import load_registry
from orchestrator.fuse import apply_delta_rule, apply_tau_rule
from orchestrator.schemas import IdentifyResponse, Candidate, Identity, NormativaAnswer, Citation
from db.mongo import init_motor, close_motor
from db.queries import (
    save_trace,
    save_access_log,
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
FUSION_METHOD = os.getenv("FUSION_METHOD", "delta")  # "delta" o "tau"


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
    """
    Endpoint de health check mejorado (H7)
    
    Verifica:
    - Estado del servicio
    - Conectividad MongoDB
    - Conteo de servicios PP2 registrados
    """
    health_status = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Verificar MongoDB
    mongo_status = "ok"
    try:
        # Obtener instancia de motor_db (inicializar si es necesario)
        # Importar dentro de la función para obtener la referencia actualizada
        import db.mongo as mongo_module
        
        if mongo_module.motor_db is None:
            db_instance = await init_motor()
        else:
            db_instance = mongo_module.motor_db
        
        # Intentar una operación simple para verificar conectividad
        await db_instance.command("ping")
    except Exception as e:
        mongo_status = "error"
        health_status["mongo_error"] = str(e)
        health_status["status"] = "degraded"
    
    health_status["services"]["mongodb"] = mongo_status
    
    # Contar servicios PP2 registrados
    try:
        roster = load_registry()
        pp2_count = len(roster) if roster else 0
        health_status["services"]["pp2_registered"] = pp2_count
    except Exception as e:
        health_status["services"]["pp2_registry"] = "error"
        health_status["pp2_registry_error"] = str(e)
    
    return health_status


@app.post("/identify-and-answer", response_model=IdentifyResponse)
async def identify_and_answer(
    request: Request,
    image: UploadFile = File(..., description="Imagen de persona para verificación (.jpg, .jpeg, .png)"),
    query: Optional[str] = Form(None, description="Pregunta sobre normativa (opcional)"),
    provider: Optional[str] = Form(None, description="Proveedor LLM (deepseek o chatgpt)"),
    k: Optional[int] = Form(None, description="Top K resultados")
):
    """
    Identificar persona usando múltiples servicios PP2 (verificación facial paralela) 
    y responder consulta usando PP1 (chatbot) si está identificada
    
    POR QUÉ este diseño:
    1. Llamadas paralelas: Consulta TODOS los servicios PP2 del registry simultáneamente
    2. Fusión de resultados: Combina respuestas usando reglas τ/δ para mayor confiabilidad
    3. Tolerancia a fallos: Si algunos servicios fallan, otros pueden compensar
    4. Decisiones claras: Retorna "identified" | "ambiguous" | "unknown" con candidatos
    
    Proceso:
    1. Cargar registry de servicios PP2
    2. Llamar en paralelo a TODOS los servicios PP2 del registry
    3. Aplicar regla de fusión (τ o δ) para combinar resultados
    4. Determinar decisión: identified/ambiguous/unknown
    5. Si identified, preguntar a PP1 (si hay query)
    6. Almacenar traza en MongoDB (access_logs)
    7. Retornar respuesta con decisión y candidatos
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Extraer headers opcionales (H7)
    user_id = request.headers.get("X-User-Id") or f"anonymous_{uuid.uuid4().hex[:8]}"
    user_type = request.headers.get("X-User-Type", "external").lower()
    # Validar user_type
    valid_user_types = ["student", "faculty", "admin", "external"]
    if user_type not in valid_user_types:
        user_type = "external"
    authorization = request.headers.get("Authorization")
    
    # Obtener IP del cliente (H7)
    client_ip = request.client.host if request.client else "unknown"
    # Anonimizar último octeto para privacidad
    if client_ip and client_ip != "unknown":
        ip_parts = client_ip.split(".")
        if len(ip_parts) == 4:
            client_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
    
    try:
        # Leer contenido del archivo de imagen
        image.file.seek(0)
        image_content = image.file.read()
        image_size = len(image_content)
        
        # Calcular hash SHA256 de imagen (H7)
        image_hash = hashlib.sha256(image_content).hexdigest()
        image_hash_prefixed = f"sha256:{image_hash}"
        
        # Validar tamaño (máximo 5 MB según especificación)
        MAX_SIZE = 5 * 1024 * 1024  # 5 MB
        if image_size > MAX_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Imagen demasiado grande: {image_size} bytes (máximo: {MAX_SIZE} bytes)"
            )
        
        # Crear objeto BytesIO para cliente PP2
        image_file = io.BytesIO(image_content)
        
        # Paso 1: Cargar registry de servicios PP2
        roster = load_registry()
        
        if not roster:
            raise HTTPException(
                status_code=500,
                detail="No hay servicios PP2 configurados en el registry"
            )
        
        # Paso 2: Llamar en paralelo a TODOS los servicios PP2 del registry
        # POR QUÉ en paralelo (aunque solo haya uno):
        # - Estructura preparada para cuando agregues más servicios
        # - Reduce latencia total cuando hay múltiples servicios
        # - Permite que servicios más rápidos respondan primero
        # - Si un servicio tiene timeout, otros pueden seguir funcionando
        # 
        # NOTA: Por ahora funciona con un solo servicio, pero la estructura
        # está lista para múltiples servicios cuando los tengas disponibles
        pp2_results = await verify_all_services(
            image_file=image_file,
            filename=image.filename or "image.jpg",
            roster=roster,
            request_id=request_id
        )
        
        # Contar timeouts y errores para logging
        timeouts = sum(1 for r in pp2_results if r.get("error", "").find("timeout") != -1)
        successful_calls = sum(1 for r in pp2_results if r.get("success", False))
        
        # Detectar "No face detected" (H7 - retornar 422)
        no_face_detected = any(
            r.get("no_face_detected", False) or 
            (r.get("status_code") == 400 and "No face detected" in str(r.get("error_details", "")))
            for r in pp2_results
        )
        
        if no_face_detected:
            raise HTTPException(
                status_code=422,
                detail="No se detectó un rostro en la imagen proporcionada"
            )
        
        # Paso 3: Aplicar regla de fusión
        # POR QUÉ fusión (aunque solo haya un servicio por ahora):
        # - Estructura preparada para múltiples servicios
        # - Con un solo servicio, la fusión simplemente valida contra threshold
        # - Cuando agregues más servicios, combinará sus respuestas
        # - Regla δ (delta) es más flexible que τ (tau)
        if FUSION_METHOD.lower() == "tau":
            fusion_result = apply_tau_rule(pp2_results, threshold=THRESHOLD, margin=MARGIN)
        else:
            fusion_result = apply_delta_rule(pp2_results, threshold=THRESHOLD, margin=MARGIN)
        
        # Extraer información de la fusión
        decision = fusion_result.get("decision", "unknown")
        confidence = fusion_result.get("confidence", 0.0)
        identity = fusion_result.get("identity")
        candidates = fusion_result.get("candidates", [])
        
        # Determinar si está identificada (para compatibilidad y lógica PP1)
        person_identified = (decision == "identified")
        person_id = identity.get("person_id") if identity else None
        person_name = identity.get("name") if identity else None
        
        # Paso 4: Preguntar a PP1 (solo si está identificada Y hay query)
        pp1_result = None
        answer = ""
        normativa_answer = None
        
        if person_identified and query:
            pp1_result = await ask_pp1(
                message=query,
                provider=provider,
                k=k
            )
            
            if not pp1_result.get("success"):
                # No fallar si PP1 falla, solo registrar
                answer = f"Error al consultar normativa: {pp1_result.get('error', 'Error desconocido')}"
            else:
                answer = pp1_result.get("answer", "No se pudo obtener una respuesta.")
                
                # Construir normativa_answer con citas normalizadas
                citations = pp1_result.get("citations", [])
                citation_list = [
                    Citation(
                        doc=c.get("doc", "Documento desconocido"),
                        page=c.get("page", "N/A"),
                        url=c.get("url")
                    )
                    for c in citations
                ]
                
                normativa_answer = NormativaAnswer(
                    text=answer,
                    citations=citation_list
                )
        elif decision == "ambiguous":
            answer = f"Identificación ambigua. Confianza: {confidence:.2f}. Múltiples candidatos encontrados."
        elif decision == "unknown":
            answer = f"Persona no identificada. Confianza: {confidence:.2f} (umbral requerido: {THRESHOLD:.2f})"
        else:
            answer = "Consulta no proporcionada."
        
        # Calcular tiempo de procesamiento
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Paso 5: Almacenar access log en MongoDB (H7)
        # Estructura según especificación
        access_log_data = {
            "request_id": request_id,
            "ts": datetime.utcnow().isoformat(),
            "route": "/identify-and-answer",
            "user": {
                "id": user_id,
                "type": user_type,
                "role": "basic"  # Por defecto, puede extenderse
            },
            "input": {
                "has_image": True,
                "has_question": bool(query),
                "image_hash": image_hash_prefixed,
                "size_bytes": image_size
            },
            "decision": decision,
            "identity": identity if identity else None,
            "timing_ms": round(processing_time_ms, 2),
            "status_code": 200,
            "errors": None,
            "pp2_summary": {
                "queried": len(roster),
                "successful": successful_calls,
                "timeouts": timeouts
            },
            "pp1_used": bool(pp1_result and pp1_result.get("success")),
            "ip": client_ip
        }
        
        await save_access_log(access_log_data)
        
        # Paso 6: Construir respuesta con candidatos
        # Convertir candidatos a formato Candidate
        candidate_list = [
            Candidate(
                person_id=c.get("person_id"),
                name=c.get("name"),
                score=c.get("score", 0.0),
                service_count=c.get("service_count"),
                services=c.get("services")
            )
            for c in candidates
        ]
        
        identity_obj = None
        if identity:
            identity_obj = Identity(
                name=identity.get("name"),
                person_id=identity.get("person_id"),
                score=identity.get("score", 0.0)
            )
        
        # Retornar respuesta
        return IdentifyResponse(
            decision=decision,
            identity=identity_obj,
            candidates=candidate_list,
            person_identified=person_identified,  # Compatibilidad
            answer=answer,  # Compatibilidad (mismo texto que normativa_answer.text si existe)
            confidence=confidence,
            person_id=person_id,  # Compatibilidad
            normativa_answer=normativa_answer,  # Respuesta normativa con citas
            pp1_response=pp1_result,
            pp2_response=fusion_result,  # Resultado de fusión completo
            timing_ms=processing_time_ms,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException as e:
        # Guardar access log de error HTTP (H7)
        processing_time_ms = (time.time() - start_time) * 1000
        try:
            error_access_log = {
                "request_id": request_id,
                "ts": datetime.utcnow().isoformat(),
                "route": "/identify-and-answer",
                "user": {
                    "id": user_id if 'user_id' in locals() else "unknown",
                    "type": user_type if 'user_type' in locals() else "external",
                    "role": "basic"
                },
                "input": {
                    "has_image": 'image_content' in locals(),
                    "has_question": 'query' in locals() and bool(query),
                    "image_hash": image_hash_prefixed if 'image_hash_prefixed' in locals() else None,
                    "size_bytes": image_size if 'image_size' in locals() else 0
                },
                "decision": "unknown",
                "identity": None,
                "timing_ms": round(processing_time_ms, 2),
                "status_code": e.status_code,
                "errors": e.detail,
                "pp2_summary": {"queried": 0, "successful": 0, "timeouts": 0},
                "pp1_used": False,
                "ip": client_ip if 'client_ip' in locals() else "unknown"
            }
            await save_access_log(error_access_log)
        except Exception:
            pass  # No fallar si no se puede guardar el log
        raise
    except Exception as e:
        # Almacenar access log de error interno (H7)
        processing_time_ms = (time.time() - start_time) * 1000
        try:
            error_access_log = {
                "request_id": request_id,
                "ts": datetime.utcnow().isoformat(),
                "route": "/identify-and-answer",
                "user": {
                    "id": user_id if 'user_id' in locals() else "unknown",
                    "type": user_type if 'user_type' in locals() else "external",
                    "role": "basic"
                },
                "input": {
                    "has_image": 'image_content' in locals(),
                    "has_question": 'query' in locals() and bool(query),
                    "image_hash": image_hash_prefixed if 'image_hash_prefixed' in locals() else None,
                    "size_bytes": image_size if 'image_size' in locals() else 0
                },
                "decision": "unknown",
                "identity": None,
                "timing_ms": round(processing_time_ms, 2),
                "status_code": 500,
                "errors": str(e),
                "pp2_summary": {"queried": 0, "successful": 0, "timeouts": 0},
                "pp1_used": False,
                "ip": client_ip if 'client_ip' in locals() else "unknown"
            }
            await save_access_log(error_access_log)
        except Exception:
            pass  # No fallar si no se puede guardar el log
        
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


