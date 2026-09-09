"""Defense in depth for common secrets; not a data-loss-prevention guarantee."""

import re
from typing import Any

_KEY = re.compile(r"password|passwd|secret|token|api.?key|authorization|cookie|credential|private.?key", re.I)
_PATTERNS = (
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S),
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@"),
)


def redact(data: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    applied: set[str] = set()

    def visit(value: Any) -> Any:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                safe_key = visit(key)
                if _KEY.search(key):
                    result[safe_key] = "[REDACTED]"
                    applied.add("sensitive_field")
                else:
                    result[safe_key] = visit(item)
            return result
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str):
            for pattern in _PATTERNS:
                value, count = pattern.subn("[REDACTED]", value)
                if count:
                    applied.add("secret_pattern")
        return value

    return visit(data), tuple(sorted(applied))
