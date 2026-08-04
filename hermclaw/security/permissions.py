"""Filesystem permission helpers.

Checks and enforces tools.filesystem_scope: tool-initiated filesystem
access is confined to the profile's own workspace directory by default.
Also checks permissions on sensitive files Hermclaw itself owns (state.db,
hermclaw.yaml) -- used by `hermclaw doctor`.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


class PathOutsideScopeError(Exception):
    pass


def ensure_within_scope(path: str | os.PathLike, scope_root: str | os.PathLike) -> Path:
    """Resolve `path` and confirm it lives within `scope_root`. Raises
    PathOutsideScopeError otherwise. Used by any tool that writes/reads
    files on the agent's behalf."""
    resolved = Path(path).expanduser().resolve()
    root = Path(scope_root).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathOutsideScopeError(
            f"Path '{resolved}' is outside the allowed filesystem scope '{root}'"
        ) from exc
    return resolved


def ensure_dir(path: str | os.PathLike, mode: int = 0o700) -> Path:
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True, mode=mode)
    return p


def check_file_permissions(path: str | os.PathLike, max_mode: int = 0o600) -> list[str]:
    """Returns human-readable issues if `path` is readable/writable by
    anyone beyond its owner. Hermclaw's state.db holds full conversation
    history and hermclaw.yaml can hold *_env references pointing at real
    secrets -- both deserve owner-only permissions, and `hermclaw doctor`
    flags it plainly (not silently) if a platform or a manual `chmod`
    left them wider than that."""
    path = Path(path)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        return [f"could not stat {path}: {exc}"]
    excess = mode & ~max_mode
    if excess:
        return [f"{path} has mode {oct(mode)} -- expected at most {oct(max_mode)} (owner read/write only)"]
    return []
