# src/playbook/infrastructure/process.py
import subprocess
import shlex
from typing import Tuple
import os

from ..domain.ports import ProcessRunner


class ShellProcessRunner(ProcessRunner):
    """Shell command execution adapter"""

    def run_command(
        self, command: str, timeout: int, interactive: bool = False
    ) -> Tuple[int, str, str]:
        """Run shell command and return exit code, stdout, stderr"""
        # Expand environment variables
        command = os.path.expandvars(command)
        command = os.path.expanduser(command)

        try:
            if interactive:
                # For interactive commands, use subprocess but don't capture output
                # This allows stdin/stdout/stderr to be connected to the terminal
                result = subprocess.run(
                    command,
                    shell=True,
                    stdin=None,  # Use terminal's stdin
                    stdout=None,  # Output goes to terminal
                    stderr=None,  # Errors go to terminal
                    timeout=timeout,
                )
                return result.returncode, "", ""
            else:
                # Use shell=True to support pipes, redirections, and multi-line scripts
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,  # Capture stdout/stderr
                    text=True,
                    timeout=timeout,
                )
                return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return 1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", f"Error executing command: {str(e)}"
