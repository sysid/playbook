# src/playbook/cli/commands/view_dag.py
"""View DAG command implementation."""

import subprocess
import sys
import tempfile
from pathlib import Path

import typer

from ..common import console, get_parser, handle_error_and_exit
from ...infrastructure.visualization import GraphvizVisualizer
from ...domain.exceptions import ParseError, SystemDependencyError, FileOperationError


def view_dag(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    keep_dot: bool = typer.Option(False, "--keep-dot", help="Also save DOT file"),
    no_open: bool = typer.Option(
        False, "--no-open", help="Don't auto-open the PNG file"
    ),
):
    """View runbook DAG as PNG image"""
    try:
        parser = get_parser()
        visualizer = GraphvizVisualizer()

        # Check if dot binary is available
        try:
            subprocess.run(["dot", "-V"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise SystemDependencyError(
                "Graphviz 'dot' binary not found",
                suggestion="""Install Graphviz on your system:
• macOS: brew install graphviz
• Ubuntu/Debian: sudo apt-get install graphviz
• CentOS/RHEL: sudo yum install graphviz
• Windows: Download from https://graphviz.org/download/"""
            )

        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        try:
            runbook = parser.parse(str(file))
        except FileNotFoundError:
            raise ParseError(
                f"Runbook file not found: {file}",
                suggestion="Check the file path and ensure the file exists"
            )
        except Exception as e:
            raise ParseError(
                f"Failed to parse runbook: {str(e)}",
                context={"file": str(file)},
                suggestion="Check the TOML syntax and ensure all required fields are present"
            )

        # Always save PNG in same directory as TOML file
        png_file = file.with_suffix(".png")

        # DOT file: save if requested, otherwise use temp file
        if keep_dot:
            dot_file = file.with_suffix(".dot")
        else:
            dot_file = Path(tempfile.mktemp(suffix=".dot"))

        try:
            # Export to DOT
            console.print("Generating DOT file...")
            try:
                visualizer.export_dot(runbook, str(dot_file))
            except Exception as e:
                raise FileOperationError(
                    f"Failed to generate DOT file: {str(e)}",
                    context={"dot_file": str(dot_file)},
                    suggestion="Check file permissions and disk space"
                )

            # Convert DOT to PNG using Graphviz
            console.print(f"Converting to PNG: {png_file}")
            try:
                subprocess.run(
                    ["dot", "-Tpng", str(dot_file), "-o", str(png_file)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                raise SystemDependencyError(
                    f"Graphviz conversion failed: {e.stderr}",
                    context={"command": "dot -Tpng", "stderr": e.stderr},
                    suggestion="Check that Graphviz is properly installed and the DOT file is valid"
                )

            # Open the PNG file unless disabled
            if not no_open:
                console.print("Opening PNG file...")
                try:
                    # Try to open with default system viewer
                    if sys.platform == "darwin":  # macOS
                        subprocess.run(["open", str(png_file)], check=True)
                    elif sys.platform == "linux":  # Linux
                        subprocess.run(["xdg-open", str(png_file)], check=True)
                    elif sys.platform == "win32":  # Windows
                        subprocess.run(["start", str(png_file)], shell=True, check=True)
                    else:
                        console.print(
                            f"[yellow]Cannot auto-open on this platform. Please open manually: {png_file}[/yellow]"
                        )
                except subprocess.CalledProcessError:
                    console.print(
                        f"[yellow]Could not auto-open file. Please open manually: {png_file}[/yellow]"
                    )

            # Show success messages
            console.print(
                f"[bold green]DAG visualization saved: {png_file}[/bold green]"
            )
            if keep_dot:
                console.print(f"[bold green]DOT file saved: {dot_file}[/bold green]")

        finally:
            # Clean up temporary DOT file if not keeping it
            if not keep_dot and dot_file.exists():
                dot_file.unlink()

    except Exception as e:
        handle_error_and_exit(e, "DAG visualization", ctx.params.get('verbose', False))
