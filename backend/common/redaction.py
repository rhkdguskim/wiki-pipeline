"""Secret redaction shared by persisted observations and streamed events."""
from __future__ import annotations

import re
from typing import Any

_CREDENTIAL_KEYS = frozenset({
    "password", "passwd", "pwd", "token", "access_token", "refresh_token",
    "api_key", "apikey", "secret", "authorization",
})

_SECRET_VALUE_RE = re.compile(
    r"(?P<prefix>(?:[\"']?(?:password|passwd|pwd|token|access_token|refresh_token|"
    r"api[_-]?key|apikey|secret|authorization)[\"']?\s*[:=]\s*[\"']?)"
    r"(?:bearer\s+)?)(?P<secret>[^\s,}\]\"']+)",
    re.IGNORECASE,
)
_URL_CREDENTIAL_RE = re.compile(
    r"(?P<prefix>\b[a-z][a-z0-9+.-]*://[^\s/:@]+:)(?P<secret>[^\s@/]+)(?=@)",
    re.IGNORECASE,
)


def redact_text(value: str) -> str:
    """Mask credential-like assignments and credentials embedded in URLs."""
    if not value:
        return value
    redacted = _SECRET_VALUE_RE.sub(
        lambda match: match.group("prefix") + "***REDACTED***", value,
    )
    return _URL_CREDENTIAL_RE.sub(
        lambda match: match.group("prefix") + "***REDACTED***", redacted,
    )


def redact_data(value: Any) -> Any:
    """Recursively redact mappings and containers before they cross a boundary."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_name = str(key).lower().replace("-", "_")
            if key_name in _CREDENTIAL_KEYS:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_data(item)
        return redacted
    if isinstance(value, (list, tuple, set)):
        return [redact_data(item) for item in value]
    return value
