# src/playbook/config/__init__.py
"""Configuration management for Playbook."""

from .manager import (
    PlaybookConfig,
    DatabaseConfig,
    ExecutionConfig,
    LoggingConfig,
    UIConfig,
    ConfigManager,
    config_manager
)

# Backward compatibility - keep the original load_config function
def load_config(config_path: str = None) -> dict:
    """Load configuration (backward compatibility)."""
    config = config_manager.load_config(config_path)
    return {
        "state_path": config.database.path,
        "timeout": config.database.timeout,
        "max_retries": config.execution.max_retries,
        "log_level": config.logging.level,
    }

__all__ = [
    "PlaybookConfig",
    "DatabaseConfig",
    "ExecutionConfig",
    "LoggingConfig",
    "UIConfig",
    "ConfigManager",
    "config_manager",
    "load_config"
]