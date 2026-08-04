"""Web channel: a minimal, self-contained chat widget served directly by
the gateway -- no external dependency beyond FastAPI, which the gateway
already requires. One WebSocket per browser tab; the FastAPI app is
constructor-injectable so the shared contract test can drive it entirely
in-process via an ASGI transport, no real socket required.
"""

from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

logger = structlog.get_logger(__name__)

_WIDGET_HTML = """\
<!doctype html>
<html><head><meta charset="utf-8"><title>Hermclaw</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
#log { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; height: 60vh; overflow-y: auto; }
.msg { margin: 0.4rem 0; }
.user { color: #1a5fb4; } .agent { color: #1a1a1a; }
#row { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
#input { flex: 1; padding: 0.5rem; }
</style></head>
<body>
<h3>Hermclaw</h3>
<div id="log"></div>
<div id="row"><input id="input" autofocus placeholder="Message Hermclaw..."/><button id="send">Send</button></div>
<script>
const log = document.getElementById('log');
const input = document.getElementById('input');
const ws = new WebSocket(`ws://${location.host}/ws`);
function append(cls, text) {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.textContent = (cls === 'user' ? 'you: ' : 'hermclaw: ') + text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
ws.onmessage = (ev) => append('agent', ev.data);
function sendMsg() {
  const text = input.value.trim();
  if (!text) return;
  append('user', text);
  ws.send(text);
  input.value = '';
}
document.getElementById('send').onclick = sendMsg;
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMsg(); });
</script>
</body></html>
"""


class WebChannel(ChannelAdapter):
    def __init__(self, app: Optional[FastAPI] = None) -> None:
        super().__init__()
        self.app = app if app is not None else FastAPI()
        self._connections: dict[str, WebSocket] = {}
        self._started = False
        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.get("/")
        async def index() -> str:  # type: ignore[unused-ignore]
            from fastapi.responses import HTMLResponse

            return HTMLResponse(_WIDGET_HTML)

        @self.app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            conn_id = str(uuid.uuid4())
            self._connections[conn_id] = websocket
            try:
                while True:
                    text = await websocket.receive_text()
                    await self._emit(IncomingMessage(channel="web", external_user_id=conn_id, text=text, raw=websocket))
            except WebSocketDisconnect:
                pass
            finally:
                self._connections.pop(conn_id, None)

    async def start(self) -> None:
        # Route registration already happened at construction time; the
        # gateway is what actually binds a socket and serves self.app
        # (see body/gateway.py), so "starting" here just flips the flag
        # the contract test and health() check against.
        self._started = True

    async def stop(self) -> None:
        self._started = False
        for conn_id, ws in list(self._connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
            self._connections.pop(conn_id, None)

    async def send(self, message: OutgoingMessage) -> None:
        ws = self._connections.get(message.reply_to)
        if ws is None:
            logger.warning("web_channel.unknown_connection", reply_to=message.reply_to)
            return
        await ws.send_text(message.text)

    def health(self) -> ChannelHealth:
        return ChannelHealth(
            connected=self._started, detail=f"{len(self._connections)} open connection(s)" if self._started else "not started"
        )
