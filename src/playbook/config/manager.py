# src/playbook/config/manager.py
"""Configuration management system."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from pydantic import BaseModel, Field, field_validator
from rich.console import Console

from ..domain.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = Field(
        default="~/.config/playbook/run.db", description="Database file path"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="Database timeout in seconds"
    )
    backup_enabled: bool = Field(default=True, description="Enable automatic backups")
    backup_count: int = Field(
        default=5, ge=1, le=50, description="Number of backups to keep"
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v):
        """Expand user path and ensure parent directory exists."""
        expanded_path = Path(v).expanduser()
        expanded_path.parent.mkdir(parents=True, exist_ok=True)
        return str(expanded_path)


class ExecutionConfig(BaseModel):
    """Execution configuration."""

    default_timeout: int = Field(
        default=300, ge=1, description="Default command timeout in seconds"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Default maximum retries"
    )
    interactive_timeout: int = Field(
        default=1800, ge=30, description="Interactive command timeout"
    )
    parallel_execution: bool = Field(
        default=False, description="Enable parallel node execution"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    max_size_mb: int = Field(
        default=10, ge=1, le=100, description="Max log file size in MB"
    )
    backup_count: int = Field(
        default=3, ge=1, le=10, description="Number of log files to keep"
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid logging level. Must be one of: {valid_levels}")
        return v.upper()


class UIConfig(BaseModel):
    """User interface configuration."""

    progress_style: str = Field(default="bar", description="Progress display style")
    color_theme: str = Field(
        default="auto", description="Color theme (auto/light/dark/none)"
    )
    show_timestamps: bool = Field(default=True, description="Show timestamps in output")
    compact_output: bool = Field(default=False, description="Use compact output format")


class PlaybookConfig(BaseModel):
    """Main configuration model."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    environment: str = Field(default="production", description="Environment name")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment name."""
        valid_envs = ["development", "testing", "production"]
        if v not in valid_envs:
            raise ValueError(f"Invalid environment. Must be one of: {valid_envs}")
        return v


class ConfigManager:
    """Manages configuration loading, validation, and environment-specific overrides."""

    def __init__(self):
        self.console = Console()
        self._config: Optional[PlaybookConfig] = None
        self._config_paths = self._get_config_paths()

    def _get_config_paths(self) -> list[Path]:
        """Get ordered list of configuration file paths to check."""
        paths = []

        # 1. Environment-specific config file
        env = os.getenv("PLAYBOOK_ENV", "production")
        if env_config := os.getenv("PLAYBOOK_CONFIG"):
            paths.append(Path(env_config))

        # 2. Local config file
        if Path("playbook.toml").exists():
            paths.append(Path("playbook.toml"))

        # 3. User config directory
        user_config_dir = Path.home() / ".config" / "playbook"
        paths.append(user_config_dir / f"{env}.toml")
        paths.append(user_config_dir / "config.toml")

        # 4. System config directory
        if os.name != "nt":  # Unix-like systems
            paths.append(Path("/etc/playbook/config.toml"))

        return paths

    def load_config(self, config_path: Optional[str] = None) -> PlaybookConfig:
        """Load configuration from file or environment."""
        if self._config:
            return self._config

        config_data = {}

        # Load from specified file or discover config files
        if config_path:
            config_data = self._load_config_file(Path(config_path))
        else:
            config_data = self._load_config_discovery()

        # Apply environment variable overrides
        config_data = self._apply_env_overrides(config_data)

        try:
            self._config = PlaybookConfig(**config_data)
            logger.info(
                f"Configuration loaded for environment: {self._config.environment}"
            )
            return self._config
        except Exception as e:
            raise ConfigurationError(
                f"Invalid configuration: {str(e)}",
                suggestion="Check your configuration file syntax and required fields",
            )

    def _load_config_discovery(self) -> Dict[str, Any]:
        """Load configuration using file discovery."""
        config_data = {}

        for config_path in self._config_paths:
            if config_path.exists():
                try:
                    file_data = self._load_config_file(config_path)
                    # Merge configurations (later files override earlier ones)
                    config_data = self._merge_configs(config_data, file_data)
                    logger.debug(f"Loaded config from: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")

        return config_data

    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from a TOML file."""
        try:
            import tomllib

            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except ImportError:
            raise ConfigurationError(
                "TOML library not available",
                suggestion="Install tomllib or use Python 3.11+",
            )
        except FileNotFoundError:
            raise ConfigurationError(
                f"Configuration file not found: {config_path}",
                suggestion="Create a configuration file or check the path",
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to parse configuration file {config_path}: {str(e)}",
                suggestion="Check the TOML syntax in your configuration file",
            )

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides."""
        env_mappings = {
            "PLAYBOOK_ENV": "environment",
            "PLAYBOOK_DB_PATH": "database.path",
            "PLAYBOOK_LOG_LEVEL": "logging.level",
            "PLAYBOOK_LOG_FILE": "logging.file_path",
            "PLAYBOOK_MAX_RETRIES": "execution.max_retries",
            "PLAYBOOK_DEFAULT_TIMEOUT": "execution.default_timeout",
        }

        for env_var, config_path in env_mappings.items():
            if value := os.getenv(env_var):
                self._set_nested_value(
                    config_data, config_path, self._convert_env_value(value)
                )

        return config_data

    def _merge_configs(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """Set a nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Try boolean
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # Try integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string
        return value

    def get_config(self) -> PlaybookConfig:
        """Get the current configuration."""
        if not self._config:
            return self.load_config()
        return self._config

    def reload_config(self, config_path: Optional[str] = None) -> PlaybookConfig:
        """Reload configuration from file."""
        self._config = None
        return self.load_config(config_path)

    def create_template(
        self, output_path: Path, environment: str = "development"
    ) -> None:
        """Create a configuration template file."""
        template_config = PlaybookConfig(environment=environment)

        template_content = f"""# Playbook Configuration Template - {environment.title()} Environment
# This file uses TOML format. See https://toml.io for syntax reference.

environment = "{environment}"

[database]
# Database file path (supports ~ for home directory)
path = "{template_config.database.path}"
# Database connection timeout in seconds
timeout = {template_config.database.timeout}
# Enable automatic database backups
backup_enabled = {str(template_config.database.backup_enabled).lower()}
# Number of backup files to keep
backup_count = {template_config.database.backup_count}

[execution]
# Default timeout for commands in seconds
default_timeout = {template_config.execution.default_timeout}
# Default maximum retry attempts for failed nodes
max_retries = {template_config.execution.max_retries}
# Timeout for interactive commands in seconds
interactive_timeout = {template_config.execution.interactive_timeout}
# Enable parallel execution of independent nodes (experimental)
parallel_execution = {str(template_config.execution.parallel_execution).lower()}

[logging]
# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
level = "{template_config.logging.level}"
# Log file path (leave empty for console only)
file_path = ""
# Maximum log file size in MB before rotation
max_size_mb = {template_config.logging.max_size_mb}
# Number of rotated log files to keep
backup_count = {template_config.logging.backup_count}

[ui]
# Progress display style
progress_style = "{template_config.ui.progress_style}"
# Color theme: auto, light, dark, none
color_theme = "{template_config.ui.color_theme}"
# Show timestamps in output
show_timestamps = {str(template_config.ui.show_timestamps).lower()}
# Use compact output format
compact_output = {str(template_config.ui.compact_output).lower()}
"""

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(template_content)
            self.console.print(
                f"[green]Created configuration template: {output_path}[/green]"
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create configuration template: {str(e)}",
                suggestion="Check file permissions and directory access",
            )


# Global configuration manager instance
config_manager = ConfigManager()
