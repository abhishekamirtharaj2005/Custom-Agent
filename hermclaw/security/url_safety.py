"""URL safety validation.

Validates URLs before the agent fetches them, protecting against:
- SSRF via private/internal IPs (127.0.0.1, 10.x, 192.168.x, etc.)
- Dangerous protocols (file://, ftp://, etc.)
- Known-malicious domains (extensible blocklist)
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}

# Domains the agent should never fetch (extensible)
_BLOCKED_DOMAINS: set[str] = set()

# Patterns for metadata endpoints (cloud SSRF targets)
_METADATA_PATHS = re.compile(
    r"/(latest/meta-data|computeMetadata|metadata\.google|instance|opc/v[12])", re.IGNORECASE
)


class UnsafeURLError(Exception):
    """Raised when a URL fails safety validation."""
    pass


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP."""
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, addr in infos:
            ip = ipaddress.ip_address(addr[0])
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                return True
    except (socket.gaierror, OSError):
        pass
    return False


def validate_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a URL for safety. Returns the normalized URL on success.
    Raises UnsafeURLError if the URL is potentially dangerous."""
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"Blocked URL scheme '{parsed.scheme}'. Only HTTP/HTTPS allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname.")

    if hostname.lower() in _BLOCKED_DOMAINS:
        raise UnsafeURLError(f"Domain '{hostname}' is on the blocklist.")

    if not allow_private and _is_private_ip(hostname):
        # Exception for localhost Ollama
        if hostname in ("localhost", "127.0.0.1") and parsed.port == 11434:
            pass
        else:
            raise UnsafeURLError(
                f"URL resolves to a private/internal IP (SSRF risk). Host: {hostname}"
            )

    if _METADATA_PATHS.search(parsed.path):
        raise UnsafeURLError("URL targets a cloud metadata endpoint (SSRF risk).")

    logger.debug("url_safety.validated", url=url)
    return url


def is_safe_url(url: str, *, allow_private: bool = False) -> bool:
    """Non-throwing variant: returns True if URL passes validation."""
    try:
        validate_url(url, allow_private=allow_private)
        return True
    except UnsafeURLError:
        return False


def add_blocked_domain(domain: str) -> None:
    """Add a domain to the blocklist at runtime."""
    _BLOCKED_DOMAINS.add(domain.lower())
    logger.info("url_safety.domain_blocked", domain=domain)
