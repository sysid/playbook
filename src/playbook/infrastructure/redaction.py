from __future__ import annotations

from collections.abc import Iterable


class Redactor:
    """Remove exact secret values before text leaves the execution boundary."""

    def __init__(self, secrets: Iterable[object] = ()) -> None:
        self._secrets = sorted(
            {str(secret) for secret in secrets if str(secret)},
            key=len,
            reverse=True,
        )

    def redact(self, value: object | None) -> str | None:
        if value is None:
            return None
        redacted = str(value)
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
