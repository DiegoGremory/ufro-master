"""
Reglas de fusión τ/δ para combinar resultados de múltiples servicios PP2

POR QUÉ necesitamos fusión:
1. Múltiples verificadores: Cada estudiante (Ana, Luis, etc.) tiene su propio servicio PP2
2. Redundancia: Si un servicio falla, otros pueden responder
3. Mayor confiabilidad: Múltiples opiniones reducen falsos positivos/negativos
4. Tolerancia a fallos: Si algunos servicios tienen timeout, otros pueden compensar

Decisiones posibles:
- "identified": Identificación clara con alta confianza (≥ threshold)
- "ambiguous": Múltiples candidatos o confianza media (entre threshold-margin y threshold)
- "unknown": No se puede identificar (confianza < threshold-margin o sin resultados)
"""
from typing import List, Dict, Any, Optional
import statistics


def _extract_candidates(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extraer candidatos de los resultados de servicios PP2
    
    POR QUÉ extraer candidatos:
    - Cada servicio PP2 puede retornar diferentes personas identificadas
    - Necesitamos agrupar por person_id para ver cuántos servicios coinciden
    - Los candidatos se ordenan por score para mostrar los más probables
    
    Args:
        results: Lista de resultados de servicios PP2
        
    Returns:
        Lista de candidatos únicos con sus scores agregados
    """
    candidates_dict = {}
    
    for result in results:
        if not result.get("success", False) or not result.get("verified", False):
            continue
        
        person_id = result.get("person_id")
        confidence = result.get("confidence", 0.0)
        service_name = result.get("service_name", "unknown")
        
        # Extraer nombre si está disponible (puede venir en raw_response)
        name = None
        raw_response = result.get("raw_response", {})
        if isinstance(raw_response, dict):
            name = raw_response.get("name") or raw_response.get("person_name")
        
        # Si no hay person_id, usar service_name como identificador
        key = person_id or service_name
        
        if key not in candidates_dict:
            candidates_dict[key] = {
                "person_id": person_id,
                "name": name or service_name,
                "scores": [],
                "services": []
            }
        
        candidates_dict[key]["scores"].append(confidence)
        candidates_dict[key]["services"].append(service_name)
    
    # Convertir a lista y calcular score promedio por candidato
    candidates = []
    for key, data in candidates_dict.items():
        avg_score = statistics.mean(data["scores"]) if data["scores"] else 0.0
        candidates.append({
            "person_id": data["person_id"],
            "name": data["name"],
            "score": round(avg_score, 4),
            "service_count": len(data["services"]),
            "services": data["services"]
        })
    
    # Ordenar por score descendente
    candidates.sort(key=lambda x: x["score"], reverse=True)
    
    return candidates


def _determine_decision(
    confidence: float,
    threshold: float,
    margin: float,
    candidates: List[Dict[str, Any]],
    successful_services: int,
    total_services: int = 1
) -> str:
    """
    Determinar decisión: identified | ambiguous | unknown
    
    POR QUÉ estas tres decisiones:
    - "identified": Confianza clara (≥ threshold) - podemos proceder con seguridad
    - "ambiguous": Confianza media (threshold-margin ≤ conf < threshold) - necesita revisión
    - "unknown": Confianza baja (< threshold-margin) - no se puede identificar
    
    Args:
        confidence: Confianza fusionada
        threshold: Umbral de decisión
        margin: Margen para zona ambigua
        candidates: Lista de candidatos
        successful_services: Número de servicios exitosos
        total_services: Total de servicios consultados
        
    Returns:
        Decisión: "identified" | "ambiguous" | "unknown"
    """
    if not candidates or successful_services == 0:
        return "unknown"
    
    adjusted_threshold = threshold - margin
    
    if confidence >= threshold:
        # Identificación clara
        return "identified"
    elif confidence >= adjusted_threshold:
        # Zona ambigua: confianza media o múltiples candidatos
        if len(candidates) > 1:
            return "ambiguous"
        # Si hay un solo candidato pero confianza media
        return "ambiguous"
    else:
        # Confianza muy baja
        return "unknown"


def apply_tau_rule(
    results: List[Dict[str, Any]], 
    threshold: float,
    margin: float = 0.1
) -> Dict[str, Any]:
    """
    Aplicar regla τ (tau) para fusión - Votación por mayoría con umbral
    
    POR QUÉ regla τ:
    - Votación democrática: cada servicio PP2 tiene el mismo peso
    - Mayoría simple: si más del 50% está de acuerdo, se acepta
    - Útil cuando todos los servicios tienen similar confiabilidad
    
    Args:
        results: Lista de resultados de servicios PP2 (cada uno con service_name)
        threshold: Valor de umbral para decisión
        margin: Margen para zona ambigua (por defecto: 0.1)
        
    Returns:
        Resultado fusionado con decisión, identidad y candidatos
    """
    if not results:
        return {
            "decision": "unknown",
            "confidence": 0.0,
            "method": "tau",
            "identity": None,
            "candidates": [],
            "total_services": 0,
            "successful_services": 0,
            "error": "No hay resultados para fusionar"
        }
    
    # Filtrar resultados exitosos (todos, no solo verificados)
    # IMPORTANTE: Considerar TODOS los resultados exitosos, incluso si is_me=False
    # El score sigue siendo válido y debe considerarse para la decisión
    successful_results = [
        r for r in results 
        if r.get("success", False)
    ]
    
    if not successful_results:
        return {
            "decision": "unknown",
            "confidence": 0.0,
            "method": "tau",
            "identity": None,
            "candidates": [],
            "total_services": len(results),
            "successful_services": 0
        }
    
    # Calcular confianza promedio de TODOS los resultados exitosos
    confidences = [r.get("confidence", 0.0) for r in successful_results]
    avg_confidence = statistics.mean(confidences)
    
    # Filtrar resultados verificados solo para extraer candidatos y decisión de mayoría
    verified_results = [r for r in successful_results if r.get("verified", False)]
    
    # Regla de mayoría: verificado si más del 50% está de acuerdo
    # Si solo hay un servicio, solo necesita cumplir el threshold
    if len(successful_results) == 1:
        verified = avg_confidence >= threshold
    else:
        majority_threshold = len(successful_results) / 2
        verified = len(verified_results) > majority_threshold
        
        # Si no hay mayoría, la confianza promedio debe ser muy alta
        if not verified and avg_confidence >= threshold:
            verified = True
    
    # Extraer candidatos (solo de resultados verificados)
    candidates = _extract_candidates(verified_results)
    
    # Determinar decisión usando la confianza promedio (no solo de verificados)
    decision = _determine_decision(
        confidence=avg_confidence,  # Usar confianza promedio de todos los exitosos
        threshold=threshold,
        margin=margin,
        candidates=candidates,
        successful_services=len(successful_results),  # Todos los exitosos
        total_services=len(results)
    )
    
    # Identidad principal (mejor candidato si está identificado)
    identity = None
    if decision == "identified" and candidates:
        best_candidate = candidates[0]
        identity = {
            "name": best_candidate.get("name"),
            "person_id": best_candidate.get("person_id"),
            "score": best_candidate.get("score")
        }
    
    return {
        "decision": decision,
        "confidence": round(avg_confidence, 4),
        "method": "tau",
        "identity": identity,
        "candidates": candidates,
        "total_services": len(results),
        "successful_services": len(successful_results),  # Todos los exitosos
        "min_confidence": min(confidences) if confidences else 0.0,
        "max_confidence": max(confidences) if confidences else 0.0,
        "verified": verified  # Mantener para compatibilidad
    }


def apply_delta_rule(
    results: List[Dict[str, Any]], 
    threshold: float, 
    margin: float = 0.1
) -> Dict[str, Any]:
    """
    Aplicar regla δ (delta) para fusión - Promedio ponderado con margen
    
    POR QUÉ regla δ:
    - Ponderación por confianza: servicios con mayor confianza tienen más peso
    - Más flexible que τ: permite que un servicio muy confiable domine
    - Margen ajustable: permite zona ambigua entre threshold-margin y threshold
    - Útil cuando algunos servicios son más confiables que otros
    
    Args:
        results: Lista de resultados de servicios PP2 (cada uno con service_name)
        threshold: Valor de umbral para decisión
        margin: Margen para ajuste de confianza (por defecto: 0.1)
        
    Returns:
        Resultado fusionado con decisión, identidad y candidatos
    """
    if not results:
        return {
            "decision": "unknown",
            "confidence": 0.0,
            "method": "delta",
            "identity": None,
            "candidates": [],
            "total_services": 0,
            "successful_services": 0,
            "error": "No hay resultados para fusionar"
        }
    
    # Filtrar resultados exitosos (incluye verificados y no verificados para ponderar)
    successful_results = [
        r for r in results 
        if r.get("success", False)
    ]
    
    if not successful_results:
        return {
            "decision": "unknown",
            "confidence": 0.0,
            "method": "delta",
            "identity": None,
            "candidates": [],
            "total_services": len(results),
            "successful_services": 0
        }
    
    # IMPORTANTE: Considerar TODOS los resultados exitosos para calcular confianza
    # Incluso si is_me=False, el score sigue siendo válido y debe considerarse
    # La verificación (is_me) solo indica si supera el threshold del servicio PP2
    # Pero nosotros usamos nuestro propio threshold para la decisión final
    all_confidences = [r.get("confidence", 0.0) for r in successful_results]
    weights = [c for c in all_confidences]  # Pesar por la confianza misma
    
    if sum(weights) == 0:
        weighted_confidence = 0.0
    else:
        weighted_confidence = sum(c * w for c, w in zip(all_confidences, weights)) / sum(weights)
    
    # Filtrar resultados verificados solo para extraer candidatos
    verified_results = [r for r in successful_results if r.get("verified", False)]
    
    # Aplicar ajuste de margen
    adjusted_threshold = threshold - margin
    
    # Extraer candidatos de resultados verificados
    candidates = _extract_candidates(verified_results)
    
    # Determinar decisión usando la confianza ponderada de todos los exitosos
    decision = _determine_decision(
        confidence=weighted_confidence,  # Confianza de todos los exitosos
        threshold=threshold,
        margin=margin,
        candidates=candidates,
        successful_services=len(successful_results),  # Todos los exitosos
        total_services=len(results)
    )
    
    # Identidad principal (mejor candidato si está identificado)
    identity = None
    if decision == "identified" and candidates:
        best_candidate = candidates[0]
        identity = {
            "name": best_candidate.get("name"),
            "person_id": best_candidate.get("person_id"),
            "score": best_candidate.get("score")
        }
    
    verified = weighted_confidence >= adjusted_threshold
    
    return {
        "decision": decision,
        "confidence": round(weighted_confidence, 4),
        "adjusted_threshold": adjusted_threshold,
        "method": "delta",
        "identity": identity,
        "candidates": candidates,
        "total_services": len(results),
        "successful_services": len(successful_results),  # Todos los exitosos
        "min_confidence": min(all_confidences) if all_confidences else 0.0,
        "max_confidence": max(all_confidences) if all_confidences else 0.0,
        "verified": verified  # Mantener para compatibilidad
    }


