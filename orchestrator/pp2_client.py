"""
Cliente para servicio PP2 - Endpoint de verificación facial
con httpx async, timeouts y trazas a service_logs
"""
import httpx
import os
import time
import uuid
from typing import Dict, Any, Optional, BinaryIO, List
from datetime import datetime
import asyncio

from db.mongo import motor_db, init_motor


PP2_URL = os.getenv("PP2_URL", "http://52.22.115.249:5000")
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
            
            success_result = {
                "success": True,
                "verified": result.get("verified", False),
                "confidence": result.get("confidence", result.get("score", 0.0)),
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
        error_result = {
            "success": False,
            "error": f"PP2 HTTP error: {e.response.status_code}",
            "status_code": e.response.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Intentar obtener cuerpo de respuesta de error
        try:
            error_body = e.response.json()
            error_result["error_details"] = error_body
        except Exception:
            error_result["error_details"] = e.response.text[:500]
        
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


async def verify_concurrent(
    images: List[tuple[BinaryIO, str]], 
    endpoint: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Verificación concurrente de múltiples imágenes contra endpoint PP2
    Todas las requests se registran en service_logs con IDs de correlación
    
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


