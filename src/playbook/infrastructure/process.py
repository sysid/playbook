# src/playbook/infrastructure/process.py
import subprocess
import os
import signal
import termios
import sys
import time
from typing import Tuple

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
                # Save terminal settings before running interactive command
                try:
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    has_term = True
                except (AttributeError, termios.error):
                    has_term = False

                # Create a new process group to ensure we can kill all child processes
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=None,  # Use terminal's stdin
                    stdout=None,  # Output goes to terminal
                    stderr=None,  # Errors go to terminal
                    preexec_fn=os.setsid,  # Create a new process group
                )

                # Wait for command to complete with timeout
                try:
                    process.wait(timeout=timeout)
                    return process.returncode, "", ""
                except subprocess.TimeoutExpired:
                    # First try gentle termination of the process group
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        # Give it a second to terminate gracefully
                        time.sleep(1)
                        if process.poll() is None:  # If still running
                            # Force kill the process group
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass  # Process already terminated

                    # Restore terminal settings
                    if has_term:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

                    # Reset terminal
                    os.system("stty sane")

                    return 1, "", f"Command timed out after {timeout} seconds"
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
            # This will only be reached for non-interactive commands
            return 1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", f"Error executing command: {str(e)}"
