"""
Cargar registry de servicios PP2 desde configuración YAML
"""
import yaml
import os
from typing import List, Dict, Any
from pathlib import Path


def load_registry(registry_path: str = None) -> List[Dict[str, Any]]:
    """
    Cargar registry de servicios PP2 desde archivo YAML
    
    Args:
        registry_path: Ruta al archivo registry.yaml
        
    Returns:
        Lista de configuraciones de servicios
    """
    if registry_path is None:
        # Por defecto conf/registry.yaml relativo a la raíz del proyecto
        project_root = Path(__file__).parent.parent
        registry_path = project_root / "conf" / "registry.yaml"
    
    if not os.path.exists(registry_path):
        # Retornar configuración de servicio único por defecto
        return [{
            "name": "pp2_default",
            "endpoint_verify": os.getenv("PP2_URL", "http://52.22.115.249:5000") + "/verify",
            "threshold": float(os.getenv("THRESHOLD", "0.75")),
            "enabled": True
        }]
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    services = config.get("services", [])
    
    # Filtrar solo servicios habilitados
    enabled_services = [
        service for service in services 
        if service.get("enabled", True)
    ]
    
    return enabled_services if enabled_services else services


def get_service_by_name(name: str, registry_path: str = None) -> Dict[str, Any]:
    """
    Obtener un servicio específico por nombre desde el registry
    
    Args:
        name: Nombre del servicio
        registry_path: Ruta al archivo registry.yaml
        
    Returns:
        Configuración del servicio o None si no se encuentra
    """
    services = load_registry(registry_path)
    
    for service in services:
        if service.get("name") == name:
            return service
    
    return None

