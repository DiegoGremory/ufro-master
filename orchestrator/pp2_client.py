"""
Cliente para servicio PP2 - Endpoint de verificación facial
con httpx async, timeouts y trazas a service_logs
"""
import httpx
import os
import time
import uuid
import io
from typing import Dict, Any, Optional, BinaryIO, List
from datetime import datetime
import asyncio

from db.mongo import motor_db, init_motor


PP2_URL = os.getenv("PP2_URL", "http://localhost:5000")
PP2_TIMEOUT = float(os.getenv("PP2_TIMEOUT", "30"))
PP2_CONNECT_TIMEOUT = float(os.getenv("PP2_CONNECT_TIMEOUT", "10"))
PP2_READ_TIMEOUT = float(os.getenv("PP2_READ_TIMEOUT", "30"))


async def _save_service_log(
    service_name: str,
    endpoint: str,
    method: str,
    request_data: Dict[str, Any],
    response_data: Dict[str, Any],
    status_code: Optional[int] = None,
    response_time_ms: float = 0.0,
    error: Optional[str] = None,
    request_id: Optional[str] = None
) -> str:
    """
    Guarda log de llamada a servicio en la colección service_logs de MongoDB
    
    Args:
        service_name: Nombre del servicio (ej: "PP2")
        endpoint: URL del endpoint llamado
        method: Método HTTP usado
        request_data: Datos de request enviados
        response_data: Datos de response recibidos
        status_code: Código de estado HTTP
        response_time_ms: Tiempo de respuesta en milisegundos
        error: Mensaje de error si existe
        request_id: ID de request opcional para correlación
        
    Returns:
        ID del log
    """
    if not motor_db:
        await init_motor()
    
    log_id = str(uuid.uuid4())
    log_entry = {
        "_id": log_id,
        "service_name": service_name,
        "endpoint": endpoint,
        "method": method,
        "request_data": request_data,
        "response_data": response_data,
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "error": error,
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow()
    }
    
    try:
        await motor_db.service_logs.insert_one(log_entry)
    except Exception as e:
        # Registrar error pero no fallar la operación principal
        print(f"Advertencia: Error al guardar log de servicio: {str(e)}")
    
    return log_id


async def verify_person(
    image_file: BinaryIO,
    filename: str,
    endpoint: Optional[str] = None,
    timeout: Optional[float] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verifica persona contra servicio PP2 (verificación facial)
    Usa httpx async con timeouts configurables y registra en service_logs
    
    Args:
        image_file: Objeto tipo archivo binario con la imagen
        filename: Nombre del archivo (debe tener extensión .jpg, .jpeg o .png)
        endpoint: URL del endpoint PP2 verify, por defecto desde variable de entorno
        timeout: Timeout de request en segundos, por defecto desde variable de entorno
        request_id: ID de request opcional para correlación en logs
        
    Returns:
        Resultado de verificación con score de confianza
    """
    url = endpoint or f"{PP2_URL}/verify"
    timeout_value = timeout or PP2_TIMEOUT
    request_id = request_id or str(uuid.uuid4())
    start_time = time.time()
    
    # Validar extensión de archivo
    valid_extensions = {'.jpg', '.jpeg', '.png'}
    file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
    if f'.{file_ext}' not in valid_extensions:
        error_result = {
            "success": False,
            "error": f"Extensión de archivo inválida. Debe ser una de: {valid_extensions}",
            "timestamp": datetime.utcnow().isoformat()
        }
        # Registrar error de validación
        await _save_service_log(
            service_name="PP2",
            endpoint=url,
            method="POST",
            request_data={"filename": filename, "file_size": 0},
            response_data=error_result,
            status_code=None,
            response_time_ms=0.0,
            error=error_result["error"],
            request_id=request_id
        )
        return error_result
    
    # Leer contenido de imagen (resetear puntero de archivo si es necesario)
    if hasattr(image_file, 'seek'):
        image_file.seek(0)
    image_content = image_file.read()
    file_size = len(image_content)
    
    # Preparar datos multipart form
    files = {
        "file": (filename, image_content, f"image/{file_ext}")
    }
    
    # Configurar timeouts con httpx.Timeout
    timeout_config = httpx.Timeout(
        connect=PP2_CONNECT_TIMEOUT,
        read=PP2_READ_TIMEOUT,
        write=timeout_value,
        pool=timeout_value
    )
    
    request_data = {
        "filename": filename,
        "file_size": file_size,
        "file_extension": file_ext,
        "endpoint": url
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(url, files=files)
            response_time_ms = (time.time() - start_time) * 1000
            
            # Intentar parsear respuesta JSON
            try:
                result = response.json()
            except Exception:
                result = {"raw_text": response.text[:500]}  # Limitar tamaño de texto
            
            response.raise_for_status()
            
            # Mapear is_me a verified (PP2 retorna is_me, no verified)
            is_me = result.get("is_me", False)
            score = result.get("score", result.get("confidence", 0.0))
            
            success_result = {
                "success": True,
                "verified": is_me,  # is_me actúa como verified
                "confidence": score,
                "person_id": result.get("person_id"),
                "raw_response": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Registrar request exitoso
            await _save_service_log(
                service_name="PP2",
                endpoint=url,
                method="POST",
                request_data=request_data,
                response_data=success_result,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error=None,
                request_id=request_id
            )
            
            return success_result
            
    except httpx.TimeoutException as e:
        response_time_ms = (time.time() - start_time) * 1000
        timeout_result = {
            "success": False,
            "error": f"PP2 service timeout after {timeout_value}s",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Registrar timeout
        await _save_service_log(
            service_name="PP2",
            endpoint=url,
            method="POST",
            request_data=request_data,
            response_data=timeout_result,
            status_code=None,
            response_time_ms=response_time_ms,
            error=timeout_result["error"],
            request_id=request_id
        )
        
        return timeout_result
        
    except httpx.HTTPStatusError as e:
        response_time_ms = (time.time() - start_time) * 1000
        
        # Intentar obtener cuerpo de respuesta de error
        error_body = None
        try:
            error_body = e.response.json()
        except Exception:
            error_body = {"raw_text": e.response.text[:500]}
        
        # Detectar "No face detected" (error 400)
        is_no_face = False
        if e.response.status_code == 400:
            error_msg = error_body.get("error", "") if isinstance(error_body, dict) else str(error_body)
            if "No face detected" in str(error_msg) or "no face" in str(error_msg).lower():
                is_no_face = True
        
        error_result = {
            "success": False,
            "error": f"PP2 HTTP error: {e.response.status_code}",
            "status_code": e.response.status_code,
            "error_details": error_body,
            "no_face_detected": is_no_face,  # Flag para detectar en api/app.py
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Registrar error HTTP
        await _save_service_log(
            service_name="PP2",
            endpoint=url,
            method="POST",
            request_data=request_data,
            response_data=error_result,
            status_code=e.response.status_code,
            response_time_ms=response_time_ms,
            error=error_result["error"],
            request_id=request_id
        )
        
        return error_result
        
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        error_result = {
            "success": False,
            "error": f"PP2 error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Registrar error general
        await _save_service_log(
            service_name="PP2",
            endpoint=url,
            method="POST",
            request_data=request_data,
            response_data=error_result,
            status_code=None,
            response_time_ms=response_time_ms,
            error=str(e),
            request_id=request_id
        )
        
        return error_result


async def verify_all_services(
    image_file: BinaryIO,
    filename: str,
    roster: List[Dict[str, Any]],
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Verificar imagen contra TODOS los servicios PP2 del roster en paralelo
    Esta es la función principal para H5 - Fusión
    
    POR QUÉ esta función:
    - Permite consultar múltiples verificadores (Ana, Luis, etc.) simultáneamente
    - Reduce latencia total (en lugar de secuencial, es paralelo)
    - Cada servicio puede tener su propio threshold y endpoint
    - Permite fusión de resultados para mayor confiabilidad
    
    Args:
        image_file: Objeto tipo archivo binario con la imagen
        filename: Nombre del archivo
        roster: Lista de servicios PP2 del registry (cada uno con name, endpoint_verify, threshold)
        request_id: ID de request base opcional para correlación
        
    Returns:
        Lista de resultados de verificación, uno por cada servicio en el roster
        Cada resultado incluye: success, verified, confidence, person_id, service_name
    """
    if not roster:
        return []
    
    base_request_id = request_id or str(uuid.uuid4())
    tasks = []
    
    # Crear una copia de la imagen para cada servicio (cada servicio necesita su propia copia)
    image_file.seek(0)
    image_content = image_file.read()
    
    for idx, service_config in enumerate(roster):
        if not service_config.get("enabled", True):
            continue
        
        service_name = service_config.get("name", f"pp2_service_{idx}")
        endpoint = service_config.get("endpoint_verify")
        service_threshold = service_config.get("threshold", 0.75)
        
        # Crear copia de la imagen para este servicio
        service_image = io.BytesIO(image_content)
        concurrent_request_id = f"{base_request_id}-{service_name}"
        
        # Llamar a verify_person con el endpoint específico del servicio
        tasks.append(
            verify_person(
                image_file=service_image,
                filename=filename,
                endpoint=endpoint,
                request_id=concurrent_request_id
            )
        )
    
    # Ejecutar todas las llamadas en paralelo
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Procesar resultados y agregar información del servicio
    processed_results = []
    service_idx = 0
    
    for idx, service_config in enumerate(roster):
        if not service_config.get("enabled", True):
            continue
        
        service_name = service_config.get("name", f"pp2_service_{idx}")
        
        if service_idx < len(results):
            result = results[service_idx]
            
            if isinstance(result, Exception):
                error_result = {
                    "success": False,
                    "error": str(result),
                    "verified": False,
                    "confidence": 0.0,
                    "service_name": service_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
                processed_results.append(error_result)
            else:
                # Agregar información del servicio al resultado
                result["service_name"] = service_name
                result["service_threshold"] = service_config.get("threshold", 0.75)
                processed_results.append(result)
            
            service_idx += 1
    
    return processed_results


async def verify_concurrent(
    images: List[tuple[BinaryIO, str]], 
    endpoint: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Verificación concurrente de múltiples imágenes contra endpoint PP2
    (Función legacy - usar verify_all_services para fusión con múltiples servicios)
    
    Args:
        images: Lista de tuplas (image_file, filename)
        endpoint: URL del endpoint PP2 verify
        request_id: ID de request base opcional para correlación
        
    Returns:
        Lista de resultados de verificación
    """
    base_request_id = request_id or str(uuid.uuid4())
    tasks = []
    
    for idx, (image_file, filename) in enumerate(images):
        # Generar ID de request único para cada request concurrente
        concurrent_request_id = f"{base_request_id}-{idx}"
        tasks.append(verify_person(image_file, filename, endpoint, request_id=concurrent_request_id))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convertir excepciones a diccionarios de error
    processed_results = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            error_result = {
                "success": False,
                "error": str(result),
                "timestamp": datetime.utcnow().isoformat()
            }
            # Registrar excepción
            await _save_service_log(
                service_name="PP2",
                endpoint=endpoint or f"{PP2_URL}/verify",
                method="POST",
                request_data={"filename": images[idx][1] if idx < len(images) else "unknown"},
                response_data=error_result,
                status_code=None,
                response_time_ms=0.0,
                error=str(result),
                request_id=f"{base_request_id}-{idx}"
            )
            processed_results.append(error_result)
        else:
            processed_results.append(result)
    
    return processed_results


