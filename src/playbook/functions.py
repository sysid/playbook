# src/playbook/functions.py
"""Built-in functions for playbook."""

import logging
import time

logger = logging.getLogger(__name__)


def notify(message: str) -> str:
    """
    Send a notification with the given message.

    Args:
        message: The message to send

    Returns:
        Confirmation message
    """
    logger.debug(f"NOTIFICATION: {message}")
    # Remove direct print - let the engine handle output
    # print(f"NOTIFICATION: {message}")
    return f"Notification sent: {message}"


def sleep(seconds: int) -> str:
    time.sleep(seconds)
    return f"done"


def throw() -> str:
    raise Exception("Intentional exception for testing purposes")
