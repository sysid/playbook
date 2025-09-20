# src/playbook/cli/commands/config.py
"""Configuration management command implementation."""

from pathlib import Path
from typing import Optional

import typer
from rich.table import Table
from rich.syntax import Syntax

from ..common import console, handle_error_and_exit
from ...config import config_manager
from ...domain.exceptions import ConfigurationError


def config_cmd(
    ctx: typer.Context,
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    init: Optional[str] = typer.Option(
        None, "--init", help="Initialize config for environment (dev/prod/test)"
    ),
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
    template: Optional[Path] = typer.Option(
        None, "--template", help="Create config template at path"
    ),
    env: str = typer.Option("development", "--env", help="Environment for template"),
):
    """Manage Playbook configuration."""
    try:
        if show:
            _show_config()
        elif init:
            _init_config(init)
        elif validate:
            _validate_config()
        elif template:
            _create_template(template, env)
        else:
            # Show help if no specific action
            console.print(ctx.get_help())
    except Exception as e:
        handle_error_and_exit(
            e, "Configuration management", debug=ctx.params.get("verbose", False)
        )


def _show_config():
    """Show current configuration."""
    try:
        config = config_manager.get_config()

        console.print("[bold]Current Playbook Configuration[/bold]\n")

        # Environment
        console.print(f"[cyan]Environment:[/cyan] {config.environment}")
        console.print()

        # Database configuration
        console.print("[bold cyan]Database Configuration[/bold cyan]")
        db_table = Table()
        db_table.add_column("Setting")
        db_table.add_column("Value")
        db_table.add_row("Path", config.database.path)
        db_table.add_row("Timeout", f"{config.database.timeout}s")
        db_table.add_row("Backup Enabled", str(config.database.backup_enabled))
        db_table.add_row("Backup Count", str(config.database.backup_count))
        console.print(db_table)
        console.print()

        # Execution configuration
        console.print("[bold cyan]Execution Configuration[/bold cyan]")
        exec_table = Table()
        exec_table.add_column("Setting")
        exec_table.add_column("Value")
        exec_table.add_row("Default Timeout", f"{config.execution.default_timeout}s")
        exec_table.add_row("Max Retries", str(config.execution.max_retries))
        exec_table.add_row(
            "Interactive Timeout", f"{config.execution.interactive_timeout}s"
        )
        exec_table.add_row(
            "Parallel Execution", str(config.execution.parallel_execution)
        )
        console.print(exec_table)
        console.print()

        # Logging configuration
        console.print("[bold cyan]Logging Configuration[/bold cyan]")
        log_table = Table()
        log_table.add_column("Setting")
        log_table.add_column("Value")
        log_table.add_row("Level", config.logging.level)
        log_table.add_row("File Path", config.logging.file_path or "(console only)")
        log_table.add_row("Max Size MB", str(config.logging.max_size_mb))
        log_table.add_row("Backup Count", str(config.logging.backup_count))
        console.print(log_table)
        console.print()

        # UI configuration
        console.print("[bold cyan]UI Configuration[/bold cyan]")
        ui_table = Table()
        ui_table.add_column("Setting")
        ui_table.add_column("Value")
        ui_table.add_row("Progress Style", config.ui.progress_style)
        ui_table.add_row("Color Theme", config.ui.color_theme)
        ui_table.add_row("Show Timestamps", str(config.ui.show_timestamps))
        ui_table.add_row("Compact Output", str(config.ui.compact_output))
        console.print(ui_table)

    except Exception as e:
        raise ConfigurationError(
            f"Failed to load configuration: {str(e)}",
            suggestion="Check your configuration file syntax or create a new one with 'playbook config --init'",
        )


def _init_config(environment: str):
    """Initialize configuration for an environment."""
    valid_envs = ["development", "testing", "production", "dev", "test", "prod"]

    # Normalize environment names
    env_map = {"dev": "development", "test": "testing", "prod": "production"}
    environment = env_map.get(environment, environment)

    if environment not in ["development", "testing", "production"]:
        raise ConfigurationError(
            f"Invalid environment: {environment}",
            suggestion=f"Use one of: {', '.join(valid_envs)}",
        )

    # Create config directory
    config_dir = Path.home() / ".config" / "playbook"
    config_path = config_dir / f"{environment}.toml"

    if config_path.exists():
        if not typer.confirm(
            f"Configuration file {config_path} already exists. Overwrite?"
        ):
            console.print("Configuration initialization cancelled.")
            return

    try:
        config_manager.create_template(config_path, environment)
        console.print(
            f"\n[green]✅ Configuration initialized for {environment} environment[/green]"
        )
        console.print(f"[dim]Config file: {config_path}[/dim]")
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("1. Edit the configuration file to customize settings")
        console.print("2. Set PLAYBOOK_ENV environment variable to activate:")
        console.print(f"   [cyan]export PLAYBOOK_ENV={environment}[/cyan]")
        console.print(
            "3. Validate configuration: [cyan]playbook config --validate[/cyan]"
        )

    except Exception as e:
        raise ConfigurationError(
            f"Failed to initialize configuration: {str(e)}",
            suggestion="Check file permissions and ensure the directory is writable",
        )


def _validate_config():
    """Validate current configuration."""
    try:
        config = config_manager.get_config()
        console.print("[green]✅ Configuration is valid[/green]")
        console.print(f"[dim]Environment: {config.environment}[/dim]")

        # Show any warnings
        warnings = []

        # Check database path accessibility
        db_path = Path(config.database.path)
        if not db_path.parent.exists():
            warnings.append(f"Database directory does not exist: {db_path.parent}")

        # Check log file path if specified
        if config.logging.file_path:
            log_path = Path(config.logging.file_path)
            if not log_path.parent.exists():
                warnings.append(f"Log directory does not exist: {log_path.parent}")

        if warnings:
            console.print("\n[yellow]⚠️ Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  • {warning}")

    except Exception as e:
        raise ConfigurationError(
            f"Configuration validation failed: {str(e)}",
            suggestion="Fix the configuration errors and try again",
        )


def _create_template(template_path: Path, environment: str):
    """Create a configuration template."""
    valid_envs = ["development", "testing", "production"]

    if environment not in valid_envs:
        raise ConfigurationError(
            f"Invalid environment: {environment}",
            suggestion=f"Use one of: {', '.join(valid_envs)}",
        )

    if template_path.exists():
        if not typer.confirm(f"File {template_path} already exists. Overwrite?"):
            console.print("Template creation cancelled.")
            return

    try:
        config_manager.create_template(template_path, environment)
        console.print("\n[green]✅ Configuration template created[/green]")
        console.print(f"[dim]Template file: {template_path}[/dim]")

        # Show a preview of the template
        if typer.confirm("Show template content?", default=True):
            content = template_path.read_text()
            syntax = Syntax(content, "toml", theme="monokai", line_numbers=True)
            console.print("\n[bold]Template Content:[/bold]")
            console.print(syntax)

    except Exception as e:
        raise ConfigurationError(
            f"Failed to create template: {str(e)}",
            suggestion="Check file permissions and ensure the directory is writable",
        )
