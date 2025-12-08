"""
Cliente para servicio PP1 - Endpoint de chatbot con normalización de citas
"""
import httpx
import os
from typing import Dict, Any, Optional, List
from datetime import datetime


PP1_URL = os.getenv("PP1_URL", "http://3.231.127.90:8081")
PP1_PROVIDER = os.getenv("PP1_PROVIDER", "deepseek")
PP1_K = int(os.getenv("PP1_K", "4"))
PP1_TIMEOUT = float(os.getenv("PP1_TIMEOUT", "30"))


def normalize_citations(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizar citas de PP1 al formato estándar esperado
    
    POR QUÉ normalizar:
    - PP1 retorna citas en formato: {"doc_id": str, "page": int|"N/A", "text": str, "score": float}
    - Necesitamos formato estándar: {"doc": str, "page": str, "url": str}
    - Permite consistencia en la API y facilita agregar URLs en el futuro
    
    Args:
        sources: Lista de citas de PP1 con formato:
            - doc_id: ID del documento (nombre del archivo sin extensión)
            - page: Número de página (int para PDFs, 1 para TXT, "N/A" si falta)
            - text: Texto del chunk (opcional, no se incluye en respuesta normalizada)
            - score: Score de relevancia (opcional, no se incluye en respuesta normalizada)
    
    Returns:
        Lista de citas normalizadas con formato:
            - doc: Nombre del documento (normalizado desde doc_id)
            - page: Número de página como string
            - url: URL del documento (opcional, puede ser None o construida)
    """
    if not sources:
        return []
    
    normalized = []
    
    for source in sources:
        if not isinstance(source, dict):
            continue
        
        # Extraer doc_id y normalizarlo a nombre de documento legible
        doc_id = source.get("doc_id", "unknown")
        doc_name = _normalize_doc_name(doc_id)
        
        # Extraer page y convertir a string
        page = source.get("page", "N/A")
        if isinstance(page, int):
            page_str = str(page)
        elif isinstance(page, str):
            page_str = page
        else:
            page_str = "N/A"
        
        # Construir URL (opcional, puede ser None si no hay base URL configurada)
        # Por ahora, construimos una URL relativa que puede ser completada después
        url = _build_document_url(doc_id, page_str)
        
        citation = {
            "doc": doc_name,
            "page": page_str,
            "url": url
        }
        
        normalized.append(citation)
    
    return normalized


def _normalize_doc_name(doc_id: str) -> str:
    """
    Normalizar doc_id a un nombre de documento legible
    
    POR QUÉ normalizar nombres:
    - doc_id viene como "REGLAMENTO-DE-CONVIVENCIA-UNIVERSITARIA" o "ReglamentodeRegimendeEstudios__2023_"
    - Necesitamos nombres más legibles para el usuario
    - Reemplaza guiones bajos y guiones por espacios, capitaliza apropiadamente
    
    Args:
        doc_id: ID del documento (nombre del archivo sin extensión)
    
    Returns:
        Nombre de documento normalizado y legible
    """
    if not doc_id or doc_id == "unknown":
        return "Documento desconocido"
    
    # Reemplazar guiones bajos y múltiples guiones por espacios
    name = doc_id.replace("_", " ").replace("-", " ")
    
    # Limpiar espacios múltiples
    name = " ".join(name.split())
    
    # Capitalizar primera letra de cada palabra (título)
    name = name.title()
    
    return name


def _build_document_url(doc_id: str, page: str) -> Optional[str]:
    """
    Construir URL del documento (opcional)
    
    POR QUÉ construir URLs:
    - PP1 no retorna URLs, pero podemos construirlas si tenemos una base URL
    - Permite enlaces directos a documentos en el futuro
    - Por ahora retorna None, pero la estructura está lista para agregar base URL
    
    Args:
        doc_id: ID del documento
        page: Número de página
    
    Returns:
        URL del documento o None si no hay base URL configurada
    """
    # Por ahora retornamos None, pero esto puede extenderse si hay una base URL
    # Ejemplo futuro: return f"{DOCUMENTS_BASE_URL}/{doc_id}#page={page}"
    return None


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
            
            # Extraer answer y sources
            answer = result.get("answer", result.get("response", ""))
            sources = result.get("sources", [])
            
            # Normalizar citas
            # NOTA: PP1 puede retornar sources como lista de strings o lista de dicts
            # Si viene como strings (formato formateado), intentamos parsear
            # Si viene como dicts (formato pipeline), normalizamos directamente
            citations = []
            if sources:
                if isinstance(sources[0], dict):
                    # Formato pipeline: lista de diccionarios
                    citations = normalize_citations(sources)
                elif isinstance(sources[0], str):
                    # Formato formateado: lista de strings como "DOC_ID (p. N)"
                    # Intentamos parsear (aunque es menos ideal)
                    citations = _parse_string_citations(sources)
            
            return {
                "success": True,
                "answer": answer,
                "citations": citations,
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


def _parse_string_citations(sources: List[str]) -> List[Dict[str, Any]]:
    """
    Parsear citas que vienen como strings formateados
    
    POR QUÉ parsear strings:
    - PP1 puede retornar sources como strings: "DOC_ID (p. N)"
    - Necesitamos extraer doc_id y page para normalizar
    - Es un fallback si PP1 no retorna el formato pipeline original
    
    Args:
        sources: Lista de strings con formato "DOC_ID (p. N)" o similar
    
    Returns:
        Lista de citas normalizadas
    """
    citations = []
    
    for source_str in sources:
        if not isinstance(source_str, str):
            continue
        
        # Intentar parsear formato "DOC_ID (p. N)" o "DOC_ID (p. N/A)"
        import re
        match = re.match(r"^(.+?)\s*\(p\.\s*([^)]+)\)$", source_str.strip())
        
        if match:
            doc_id = match.group(1).strip()
            page_str = match.group(2).strip()
            
            doc_name = _normalize_doc_name(doc_id)
            url = _build_document_url(doc_id, page_str)
            
            citations.append({
                "doc": doc_name,
                "page": page_str,
                "url": url
            })
        else:
            # Si no coincide el formato, usar el string completo como doc
            citations.append({
                "doc": _normalize_doc_name(source_str),
                "page": "N/A",
                "url": None
            })
    
    return citations


