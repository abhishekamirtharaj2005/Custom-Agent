"""Threat pattern detection and security scanning.

Detects potentially dangerous patterns in:
- Shell commands before execution
- File content before writing
- URLs before fetching
- Agent-generated code before sandbox execution

Also includes:
- OSV vulnerability checking for Python packages
- SSL certificate validation
- 1Password / Bitwarden secret source integration (stub)
"""

from __future__ import annotations

import re
import ssl
import socket
import subprocess
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Threat pattern detection
# ---------------------------------------------------------------------------


class ThreatLevel:
    CRITICAL = "critical"  # Blocks execution
    HIGH = "high"          # Blocks with override option
    MEDIUM = "medium"      # Warning
    LOW = "low"            # Informational


@dataclasses.dataclass
class ThreatMatch:
    level: str
    category: str
    pattern: str
    description: str
    matched_text: str


import dataclasses


_SHELL_THREATS = [
    (ThreatLevel.CRITICAL, "destructive", r"rm\s+-rf\s+/\s*$", "Recursive delete of root filesystem"),
    (ThreatLevel.CRITICAL, "destructive", r"rm\s+-rf\s+~", "Recursive delete of home directory"),
    (ThreatLevel.CRITICAL, "destructive", r":()\{\s*:\|:&\s*\};:", "Fork bomb detected"),
    (ThreatLevel.CRITICAL, "destructive", r"mkfs\.\w+\s+/dev/", "Format disk device"),
    (ThreatLevel.CRITICAL, "destructive", r"dd\s+if=.*of=/dev/sd", "Raw disk write"),
    (ThreatLevel.CRITICAL, "destructive", r">\s*/dev/sd[a-z]", "Redirect to disk device"),
    (ThreatLevel.HIGH, "privilege_escalation", r"chmod\s+[0-7]*777", "World-writable permissions"),
    (ThreatLevel.HIGH, "privilege_escalation", r"chmod\s+u\+s", "Set SUID bit"),
    (ThreatLevel.HIGH, "data_exfil", r"curl\s+.*\|\s*bash", "Pipe remote script to shell"),
    (ThreatLevel.HIGH, "data_exfil", r"wget\s+.*\|\s*sh", "Pipe remote script to shell"),
    (ThreatLevel.HIGH, "data_exfil", r"curl\s+-d\s+@", "POST file contents to remote"),
    (ThreatLevel.MEDIUM, "suspicious", r"nc\s+-l", "Netcat listener"),
    (ThreatLevel.MEDIUM, "suspicious", r"nmap\s+", "Network scanning"),
    (ThreatLevel.MEDIUM, "suspicious", r"base64\s+-d", "Base64 decode (potential obfuscation)"),
    (ThreatLevel.MEDIUM, "crypto", r"bitcoin|ethereum|wallet|private.?key|seed.?phrase", "Cryptocurrency-related"),
    (ThreatLevel.LOW, "info", r"sudo\s+", "Sudo usage"),
    (ThreatLevel.LOW, "info", r"pip\s+install\s+--user", "User-level package install"),
    # Windows-specific
    (ThreatLevel.CRITICAL, "destructive", r"format\s+[a-z]:\s*/[yq]", "Format drive"),
    (ThreatLevel.CRITICAL, "destructive", r"del\s+/[sf]\s+[a-z]:\\", "Force-delete system files"),
    (ThreatLevel.HIGH, "registry", r"reg\s+(delete|add)\s+HKLM", "Modify system registry"),
    (ThreatLevel.HIGH, "privilege_escalation", r"net\s+user\s+\w+\s+/add", "Create user account"),
    (ThreatLevel.MEDIUM, "suspicious", r"powershell\s+-e[nc]+\s+", "Encoded PowerShell command"),
    (ThreatLevel.MEDIUM, "suspicious", r"Invoke-WebRequest.*\|\s*iex", "Download and execute"),
]

_CODE_THREATS = [
    (ThreatLevel.HIGH, "injection", r"eval\(.*input\(", "Eval on user input"),
    (ThreatLevel.HIGH, "injection", r"exec\(.*input\(", "Exec on user input"),
    (ThreatLevel.HIGH, "injection", r"os\.system\(", "os.system() call"),
    (ThreatLevel.HIGH, "injection", r"subprocess\.call\(.*shell\s*=\s*True", "Shell injection risk"),
    (ThreatLevel.MEDIUM, "network", r"socket\.socket\(", "Raw socket creation"),
    (ThreatLevel.MEDIUM, "network", r"http\.server", "HTTP server creation"),
    (ThreatLevel.MEDIUM, "file_access", r"open\(.*/etc/passwd", "Reading system password file"),
    (ThreatLevel.MEDIUM, "file_access", r"open\(.*/etc/shadow", "Reading shadow file"),
]


class ThreatDetector:
    """Scans text for dangerous patterns."""

    def scan_command(self, command: str) -> list[ThreatMatch]:
        """Scan a shell command for threats."""
        return self._scan(command, _SHELL_THREATS)

    def scan_code(self, code: str) -> list[ThreatMatch]:
        """Scan code for threats."""
        return self._scan(code, _CODE_THREATS)

    def scan_all(self, text: str) -> list[ThreatMatch]:
        """Scan text against all threat patterns."""
        return self._scan(text, _SHELL_THREATS + _CODE_THREATS)

    def has_critical(self, threats: list[ThreatMatch]) -> bool:
        return any(t.level == ThreatLevel.CRITICAL for t in threats)

    def has_high_or_above(self, threats: list[ThreatMatch]) -> bool:
        return any(t.level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH) for t in threats)

    @staticmethod
    def _scan(text: str, patterns: list[tuple]) -> list[ThreatMatch]:
        matches = []
        for level, category, pattern, description in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                matches.append(ThreatMatch(
                    level=level,
                    category=category,
                    pattern=pattern,
                    description=description,
                    matched_text=m.group()[:100],
                ))
        return matches


# ---------------------------------------------------------------------------
# OSV vulnerability checking
# ---------------------------------------------------------------------------


class OSVChecker:
    """Check Python packages against the OSV vulnerability database."""

    OSV_API = "https://api.osv.dev/v1/query"

    async def check_package(self, package: str, version: str) -> list[dict]:
        """Check a specific package+version for known vulnerabilities."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.OSV_API, json={
                    "package": {"name": package, "ecosystem": "PyPI"},
                    "version": version,
                })
                resp.raise_for_status()
                data = resp.json()

            vulns = []
            for v in data.get("vulns", []):
                vulns.append({
                    "id": v.get("id", ""),
                    "summary": v.get("summary", ""),
                    "severity": self._extract_severity(v),
                    "fixed_in": self._extract_fixed(v, package),
                })
            return vulns
        except Exception as exc:
            logger.warning("osv.check_failed", package=package, error=str(exc)[:100])
            return []

    async def check_requirements(self, req_path: str) -> dict[str, list[dict]]:
        """Check all packages in a requirements.txt."""
        results: dict[str, list[dict]] = {}
        path = Path(req_path)
        if not path.exists():
            return results

        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            parts = re.split(r"[=<>!~]+", line)
            if len(parts) >= 2:
                pkg, ver = parts[0].strip(), parts[-1].strip()
                vulns = await self.check_package(pkg, ver)
                if vulns:
                    results[f"{pkg}=={ver}"] = vulns

        return results

    @staticmethod
    def _extract_severity(vuln: dict) -> str:
        for s in vuln.get("severity", []):
            if s.get("type") == "CVSS_V3":
                score = s.get("score", "")
                try:
                    val = float(score.split("/")[0]) if "/" in score else float(score)
                    if val >= 9.0:
                        return "CRITICAL"
                    elif val >= 7.0:
                        return "HIGH"
                    elif val >= 4.0:
                        return "MEDIUM"
                    return "LOW"
                except ValueError:
                    pass
        return "UNKNOWN"

    @staticmethod
    def _extract_fixed(vuln: dict, package: str) -> Optional[str]:
        for affected in vuln.get("affected", []):
            pkg = affected.get("package", {})
            if pkg.get("name", "").lower() == package.lower():
                for r in affected.get("ranges", []):
                    for event in r.get("events", []):
                        if "fixed" in event:
                            return event["fixed"]
        return None


# ---------------------------------------------------------------------------
# SSL certificate validation
# ---------------------------------------------------------------------------


class SSLValidator:
    """Validate SSL certificates for remote hosts."""

    def check(self, hostname: str, port: int = 443) -> dict[str, Any]:
        """Check SSL certificate for a hostname."""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    return {
                        "valid": True,
                        "hostname": hostname,
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "subject": dict(x[0] for x in cert.get("subject", [])),
                        "expires": cert.get("notAfter", ""),
                        "serial": cert.get("serialNumber", ""),
                        "version": ssock.version(),
                    }
        except ssl.SSLCertVerificationError as exc:
            return {"valid": False, "hostname": hostname, "error": str(exc)}
        except Exception as exc:
            return {"valid": False, "hostname": hostname, "error": str(exc)}


# ---------------------------------------------------------------------------
# Secret source integrations (1Password, Bitwarden)
# ---------------------------------------------------------------------------


class OnePasswordSource:
    """Retrieve secrets from 1Password CLI (op)."""

    @staticmethod
    def get_secret(reference: str) -> Optional[str]:
        """Get a secret from 1Password using op:// reference.

        Example: op://vault/item/field
        """
        try:
            result = subprocess.run(
                ["op", "read", reference],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            logger.warning("1password.read_failed", ref=reference[:20], error=result.stderr[:100])
            return None
        except FileNotFoundError:
            logger.debug("1password.cli_not_found")
            return None
        except Exception as exc:
            logger.warning("1password.error", error=str(exc)[:100])
            return None

    @staticmethod
    def is_available() -> bool:
        try:
            result = subprocess.run(["op", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


class BitwardenSource:
    """Retrieve secrets from Bitwarden CLI (bw)."""

    @staticmethod
    def get_secret(item_name: str, field: str = "password") -> Optional[str]:
        """Get a secret from Bitwarden."""
        try:
            result = subprocess.run(
                ["bw", "get", field, item_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            logger.warning("bitwarden.read_failed", item=item_name[:20])
            return None
        except FileNotFoundError:
            logger.debug("bitwarden.cli_not_found")
            return None
        except Exception as exc:
            logger.warning("bitwarden.error", error=str(exc)[:100])
            return None

    @staticmethod
    def is_available() -> bool:
        try:
            result = subprocess.run(["bw", "status"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
