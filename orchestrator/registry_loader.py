"""
Load PP2 service registry from YAML configuration
"""
import yaml
import os
from typing import List, Dict, Any
from pathlib import Path


def load_registry(registry_path: str = None) -> List[Dict[str, Any]]:
    """
    Load PP2 service registry from YAML file
    
    Args:
        registry_path: Path to registry.yaml file
        
    Returns:
        List of service configurations
    """
    if registry_path is None:
        # Default to conf/registry.yaml relative to project root
        project_root = Path(__file__).parent.parent
        registry_path = project_root / "conf" / "registry.yaml"
    
    if not os.path.exists(registry_path):
        # Return default single service configuration
        return [{
            "name": "pp2_default",
            "endpoint_verify": os.getenv("PP2_URL", "http://52.22.115.249:5000") + "/verify",
            "threshold": float(os.getenv("THRESHOLD", "0.75")),
            "enabled": True
        }]
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    services = config.get("services", [])
    
    # Filter only enabled services
    enabled_services = [
        service for service in services 
        if service.get("enabled", True)
    ]
    
    return enabled_services if enabled_services else services


def get_service_by_name(name: str, registry_path: str = None) -> Dict[str, Any]:
    """
    Get a specific service by name from registry
    
    Args:
        name: Service name
        registry_path: Path to registry.yaml file
        
    Returns:
        Service configuration or None if not found
    """
    services = load_registry(registry_path)
    
    for service in services:
        if service.get("name") == name:
            return service
    
    return None

