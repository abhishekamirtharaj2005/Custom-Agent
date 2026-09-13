"""Shared fixtures for the whole test suite.

Per the build spec's testing strategy: the default test run is fully
offline. `block_real_sockets` (autouse) fails any test that opens a real
network socket unless it's explicitly marked `@pytest.mark.live` --
that's the mechanical enforcement behind "network- and model-calling
code is exercised against fakes/stubs by default."
"""

from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path
from typing import Iterator

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: hits a real network service; excluded from the default run")


@pytest.fixture(autouse=True)
def isolated_hermclaw_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Every test gets its own throwaway HERMCLAW_HOME so tests can never
    read or write a developer's real ~/.hermclaw, and can never see state
    left behind by another test."""
    home = tmp_path / ".hermclaw"
    monkeypatch.setenv("HERMCLAW_HOME", str(home))
    yield home


@pytest.fixture(autouse=True)
def block_real_sockets(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if "live" in request.keywords:
        yield
        return

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "A test tried to open a real network connection outside a @pytest.mark.live test. "
            "Use FakeTransport / an injected fake channel client instead."
        )

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _is_loopback(addr):
        if isinstance(addr, tuple) and len(addr) >= 1:
            host = str(addr[0])
            if host in ("127.0.0.1", "::1", "localhost"):
                return True
        return False

    def _guarded_connect(self, *args, **kwargs):
        addr = args[0] if args else kwargs.get("address")
        if _is_loopback(addr):
            return real_connect(self, *args, **kwargs)
        _blocked(*args, **kwargs)

    def _guarded_connect_ex(self, *args, **kwargs):
        addr = args[0] if args else kwargs.get("address")
        if _is_loopback(addr):
            return real_connect_ex(self, *args, **kwargs)
        _blocked(*args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)

    real_create_connection = socket.create_connection

    def _guarded_create_connection(address, *args, **kwargs):
        if _is_loopback(address):
            return real_create_connection(address, *args, **kwargs)
        _blocked()

    monkeypatch.setattr(socket, "create_connection", _guarded_create_connection)
    yield


@pytest.fixture
def anthropic_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Some construction paths (build_transport) need *a* value present
    for ANTHROPIC_API_KEY to proceed past the MissingCredentialsError
    check -- they never make a live call unless the test is marked
    `live`, so a fake value is sufficient and appropriate here."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-construction-only")


@pytest.fixture
def profile_manager(tmp_path: Path):
    from hermclaw.brain.profiles import ProfileManager

    return ProfileManager(home=tmp_path)
