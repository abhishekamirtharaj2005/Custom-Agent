"""WhatsApp channel: bridges to a Node.js sidecar process (Baileys, the
only mature WhatsApp Web protocol library, which is JS-only -- there is
no viable pure-Python client) over a newline-delimited JSON-RPC protocol
on the sidecar's stdin/stdout. This is a documented exception to
Hermclaw being a pure-Python package; see ARCHITECTURE.md.

Protocol (one JSON object per line, either direction):
  Python -> sidecar (request):  {"jsonrpc":"2.0","method":"send","params":{"to":..,"text":..},"id":N}
  sidecar -> Python (response): {"jsonrpc":"2.0","id":N,"result":{...}} | {"jsonrpc":"2.0","id":N,"error":{...}}
  sidecar -> Python (notify):   {"jsonrpc":"2.0","method":"message"|"status"|"qr"|"error","params":{...}}

The subprocess is constructor-injectable so tests can drive the protocol
with a fake in-memory process instead of spawning real Node.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

logger = structlog.get_logger(__name__)

SIDECAR_DIR = Path(__file__).parent / "whatsapp_sidecar"
DEFAULT_SIDECAR_COMMAND = ["node", str(SIDECAR_DIR / "index.js")]
CALL_TIMEOUT_S = 30.0


class WhatsAppChannel(ChannelAdapter):
    def __init__(self, sidecar_command: Optional[list[str]] = None, process: Optional[Any] = None) -> None:
        super().__init__()
        self.sidecar_command = sidecar_command or DEFAULT_SIDECAR_COMMAND
        self._process = process
        self._connected = False
        self._last_qr: Optional[str] = None
        self._read_task: Optional[asyncio.Task] = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future] = {}

    async def start(self) -> None:
        if self._process is None:
            self._process = await asyncio.create_subprocess_exec(
                *self.sidecar_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        self._read_task = asyncio.create_task(self._read_loop())
        logger.info("whatsapp.sidecar_started", command=self.sidecar_command)

    async def _read_loop(self) -> None:
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
            except json.JSONDecodeError:
                logger.warning("whatsapp.bad_json_from_sidecar", raw=str(line)[:200])
                continue
            await self._handle_incoming(msg)

    async def _handle_incoming(self, msg: dict[str, Any]) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            fut = self._pending.pop(msg["id"], None)
            if fut is not None and not fut.done():
                if "error" in msg:
                    fut.set_exception(RuntimeError(str(msg["error"])))
                else:
                    fut.set_result(msg["result"])
            return

        method = msg.get("method")
        params = msg.get("params") or {}
        if method == "message":
            await self._emit(
                IncomingMessage(channel="whatsapp", external_user_id=str(params.get("from", "")), text=str(params.get("text", "")), raw=msg)
            )
        elif method == "status":
            self._connected = bool(params.get("connected", False))
        elif method == "qr":
            self._last_qr = params.get("qr")
            logger.info("whatsapp.qr_ready", detail="scan with the WhatsApp app to link this device")
        elif method == "error":
            logger.warning("whatsapp.sidecar_error", message=params.get("message"))

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        if self._process is None:
            raise RuntimeError("WhatsAppChannel._call() invoked before start()")
        req_id = self._next_id
        self._next_id += 1
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        payload = (json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": req_id}) + "\n").encode("utf-8")
        self._process.stdin.write(payload)
        drain = getattr(self._process.stdin, "drain", None)
        if drain is not None:
            await drain()
        return await asyncio.wait_for(fut, timeout=CALL_TIMEOUT_S)

    async def send(self, message: OutgoingMessage) -> None:
        await self._call("send", {"to": message.reply_to, "text": message.text})

    async def stop(self) -> None:
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, Exception):
                pass
            self._read_task = None
        if self._process is not None:
            terminate = getattr(self._process, "terminate", None)
            if terminate is not None:
                try:
                    terminate()
                except ProcessLookupError:
                    pass
            wait = getattr(self._process, "wait", None)
            if wait is not None:
                try:
                    await asyncio.wait_for(wait(), timeout=5)
                except (asyncio.TimeoutError, Exception):
                    pass
        self._connected = False

    def health(self) -> ChannelHealth:
        if not self._connected and self._last_qr:
            return ChannelHealth(connected=False, detail="awaiting QR scan -- see logs")
        return ChannelHealth(connected=self._connected, detail="sidecar" if self._connected else "not connected")
