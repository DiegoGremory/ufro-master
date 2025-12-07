"""
Fusion rules τ/δ for combining results from multiple PP2 services
"""
from typing import List, Dict, Any
import statistics


def apply_tau_rule(results: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    """
    Apply τ (tau) rule for fusion - Majority voting with threshold
    
    Args:
        results: List of results from PP2 services
        threshold: Threshold value for decision
        
    Returns:
        Fused result with verified status and average confidence
    """
    if not results:
        return {
            "verified": False,
            "confidence": 0.0,
            "method": "tau",
            "error": "No results to fuse"
        }
    
    # Filter successful results
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
    
    # Calculate average confidence
    confidences = [r.get("confidence", 0.0) for r in successful_results]
    avg_confidence = statistics.mean(confidences)
    
    # Majority rule: verified if more than 50% agree and avg confidence >= threshold
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
    Apply δ (delta) rule for fusion - Weighted average with margin
    
    Args:
        results: List of results from PP2 services
        threshold: Threshold value for decision
        margin: Margin for confidence adjustment (default: 0.1)
        
    Returns:
        Fused result with verified status and weighted confidence
    """
    if not results:
        return {
            "verified": False,
            "confidence": 0.0,
            "method": "delta",
            "error": "No results to fuse"
        }
    
    # Filter successful results
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
    
    # Calculate weighted average (weights based on individual confidence)
    confidences = [r.get("confidence", 0.0) for r in successful_results]
    weights = [c for c in confidences]  # Weight by confidence itself
    
    if sum(weights) == 0:
        weighted_confidence = 0.0
    else:
        weighted_confidence = sum(c * w for c, w in zip(confidences, weights)) / sum(weights)
    
    # Apply margin adjustment
    adjusted_threshold = threshold - margin
    
    # Verified if weighted confidence >= adjusted threshold
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


