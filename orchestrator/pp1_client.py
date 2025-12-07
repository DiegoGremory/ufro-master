"""
Cliente para servicio PP1 - Endpoint de chatbot
"""
import httpx
import os
from typing import Dict, Any, Optional
from datetime import datetime


PP1_URL = os.getenv("PP1_URL", "http://3.231.127.90:8081")
PP1_PROVIDER = os.getenv("PP1_PROVIDER", "deepseek")
PP1_K = int(os.getenv("PP1_K", "4"))
PP1_TIMEOUT = float(os.getenv("PP1_TIMEOUT", "30"))


async def ask_pp1(
    message: str, 
    provider: Optional[str] = None,
    k: Optional[int] = None,
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Consulta al servicio PP1 (chatbot)
    
    Args:
        message: Mensaje de consulta
        provider: Proveedor LLM (deepseek o chatgpt), por defecto desde variable de entorno
        k: Top K resultados, por defecto desde variable de entorno
        timeout: Timeout de request en segundos, por defecto desde variable de entorno
        
    Returns:
        Respuesta del servicio PP1 con la respuesta
    """
    url = f"{PP1_URL}/"
    provider = provider or PP1_PROVIDER
    k = k or PP1_K
    timeout = timeout or PP1_TIMEOUT
    
    payload = {
        "message": message,
        "provider": provider,
        "k": k
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "answer": result.get("answer", result.get("response", "")),
                "provider": provider,
                "k": k,
                "raw_response": result,
                "timestamp": datetime.utcnow().isoformat()
            }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "PP1 service timeout",
            "timestamp": datetime.utcnow().isoformat()
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"PP1 HTTP error: {e.response.status_code}",
            "status_code": e.response.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"PP1 error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


