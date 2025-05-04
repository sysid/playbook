# src/playbook/config.py
import tomllib  # Use tomllib from stdlib instead of tomli
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG = {
    "default_timeout_seconds": 300,
    "state_path": "~/.config/playbook/run.db",
}


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file, with fallbacks"""
    config = DEFAULT_CONFIG.copy()

    # Try to load from default location if not specified
    if not config_path:
        default_path = Path("~/.config/playbook/config.toml").expanduser()
        if default_path.exists():
            config_path = str(default_path)

    # Load from config file if it exists
    if config_path and Path(config_path).exists():
        with open(config_path, "rb") as f:
            file_config = tomllib.load(f)  # Use tomllib instead of tomli
            config.update(file_config)

    # Expand user paths
    if "state_path" in config:
        config["state_path"] = str(Path(config["state_path"]).expanduser())

    return config
