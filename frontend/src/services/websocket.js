// src/services/websocket.js — WebSocket client with auto-reconnect
const WS_URL = `ws://${window.location.hostname}:8080`;
const RECONNECT_MS = 3000;
const PING_MS      = 30_000;

export function createWSClient(onMessage) {
  let ws       = null;
  let stopped  = false;
  let pingTimer = null;

  function connect() {
    if (stopped) return;

    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log("[WS] Connected");
      onMessage({ type: "ws_status", status: "connected" });
      // Keepalive ping
      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN)
          ws.send(JSON.stringify({ type: "ping" }));
      }, PING_MS);
    };

    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };

    ws.onclose = () => {
      clearInterval(pingTimer);
      onMessage({ type: "ws_status", status: "disconnected" });
      if (!stopped) setTimeout(connect, RECONNECT_MS);
    };

    ws.onerror = () => {
      onMessage({ type: "ws_status", status: "error" });
    };
  }

  connect();

  return {
    send:  (msg) => ws?.readyState === WebSocket.OPEN && ws.send(JSON.stringify(msg)),
    close: ()    => { stopped = true; clearInterval(pingTimer); ws?.close(); },
  };
}
