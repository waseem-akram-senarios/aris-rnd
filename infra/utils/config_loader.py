"""
Configuration loader for CDK stack.
Loads YAML configuration files similar to the old ARIS project.
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(env: str = "dev") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        env: Environment name (dev, staging, prod)
    
    Returns:
        Dictionary containing configuration values
    """
    # Look for config file in config/ directory (repo root)
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "config" / f"config_{env}.yml"
    
    if not config_path.exists():
        # Fallback to config_dev.yml if specific env file doesn't exist
        config_path = repo_root / "config" / "config_dev.yml"
        if not config_path.exists():
            return {}
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config or {}


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get a nested configuration value using dot notation.
    
    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., "vpc.id")
        default: Default value if path not found
    
    Returns:
        Configuration value or default
    """
    keys = path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value

