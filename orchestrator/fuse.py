"""
Reglas de fusión τ/δ para combinar resultados de múltiples servicios PP2
"""
from typing import List, Dict, Any
import statistics


def apply_tau_rule(results: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    """
    Aplicar regla τ (tau) para fusión - Votación por mayoría con umbral
    
    Args:
        results: Lista de resultados de servicios PP2
        threshold: Valor de umbral para decisión
        
    Returns:
        Resultado fusionado con estado verificado y confianza promedio
    """
    if not results:
        return {
            "verified": False,
            "confidence": 0.0,
            "method": "tau",
            "error": "No results to fuse"
        }
    
    # Filtrar resultados exitosos
    successful_results = [
        r for r in results 
        if r.get("success", False) and r.get("verified", False)
    ]
    
    if not successful_results:
        return {
            "verified": False,
            "confidence": 0.0,
            "method": "tau",
            "total_services": len(results),
            "successful_services": 0
        }
    
    # Calcular confianza promedio
    confidences = [r.get("confidence", 0.0) for r in successful_results]
    avg_confidence = statistics.mean(confidences)
    
    # Regla de mayoría: verificado si más del 50% está de acuerdo y confianza promedio >= umbral
    majority_threshold = len(results) / 2
    verified = (
        len(successful_results) > majority_threshold and 
        avg_confidence >= threshold
    )
    
    return {
        "verified": verified,
        "confidence": avg_confidence,
        "method": "tau",
        "total_services": len(results),
        "successful_services": len(successful_results),
        "min_confidence": min(confidences) if confidences else 0.0,
        "max_confidence": max(confidences) if confidences else 0.0
    }


def apply_delta_rule(results: List[Dict[str, Any]], threshold: float, margin: float = 0.1) -> Dict[str, Any]:
    """
    Aplicar regla δ (delta) para fusión - Promedio ponderado con margen
    
    Args:
        results: Lista de resultados de servicios PP2
        threshold: Valor de umbral para decisión
        margin: Margen para ajuste de confianza (por defecto: 0.1)
        
    Returns:
        Resultado fusionado con estado verificado y confianza ponderada
    """
    if not results:
        return {
            "verified": False,
            "confidence": 0.0,
            "method": "delta",
            "error": "No results to fuse"
        }
    
    # Filtrar resultados exitosos
    successful_results = [
        r for r in results 
        if r.get("success", False)
    ]
    
    if not successful_results:
        return {
            "verified": False,
            "confidence": 0.0,
            "method": "delta",
            "total_services": len(results),
            "successful_services": 0
        }
    
    # Calcular promedio ponderado (pesos basados en confianza individual)
    confidences = [r.get("confidence", 0.0) for r in successful_results]
    weights = [c for c in confidences]  # Pesar por la confianza misma
    
    if sum(weights) == 0:
        weighted_confidence = 0.0
    else:
        weighted_confidence = sum(c * w for c, w in zip(confidences, weights)) / sum(weights)
    
    # Aplicar ajuste de margen
    adjusted_threshold = threshold - margin
    
    # Verificado si confianza ponderada >= umbral ajustado
    verified = weighted_confidence >= adjusted_threshold
    
    return {
        "verified": verified,
        "confidence": weighted_confidence,
        "adjusted_threshold": adjusted_threshold,
        "method": "delta",
        "total_services": len(results),
        "successful_services": len(successful_results),
        "min_confidence": min(confidences) if confidences else 0.0,
        "max_confidence": max(confidences) if confidences else 0.0
    }


