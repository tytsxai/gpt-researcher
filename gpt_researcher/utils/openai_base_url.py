from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_openai_base_url(value: str) -> str:
    """
    Normalize OpenAI-compatible base URLs.

    - Trims whitespace
    - Removes trailing slashes
    - Appends /v1 only when the URL has no path (e.g. http://host:port)
    """
    if value is None:
        return ""

    normalized = value.strip().rstrip("/")
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    path = (parsed.path or "").rstrip("/")

    if path in ("", "/"):
        parsed = parsed._replace(path="/v1")
        return urlunparse(parsed).rstrip("/")

    return normalized

