# src/playbook/infrastructure/process.py
import subprocess
import shlex
from typing import Tuple
import os

from ..domain.ports import ProcessRunner


class ShellProcessRunner(ProcessRunner):
    """Shell command execution adapter"""

    def run_command(self, command: str, timeout: int) -> Tuple[int, str, str]:
        """Run shell command and return exit code, stdout, stderr"""
        # Expand environment variables
        command = os.path.expandvars(command)
        command = os.path.expanduser(command)

        try:
            # Using subprocess.run with captured output
            result = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return 1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", f"Error executing command: {str(e)}"
