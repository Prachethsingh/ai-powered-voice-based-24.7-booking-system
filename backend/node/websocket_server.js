/**
 * websocket_server.js — Secure WebSocket for Live Dashboard
 *
 * Security:
 *  - JWT token verification on connect
 *  - Origin whitelist
 *  - Rate limiting per client
 *  - Message sanitization
 */
import { WebSocketServer } from "ws";
import { JWTHelper, RateLimiter, sanitizeString } from "./auth.js";

export class DashboardWSServer {
  constructor({ port, jwtSecret, allowedOrigins }) {
    this.port = port;
    this.jwt = new JWTHelper(jwtSecret);
    this.allowedOrigins = allowedOrigins || ["http://localhost:3000"];
    this.rateLimiter = new RateLimiter(30, 10_000); // 30 msgs / 10s
    this.wss = null;
    this.clients = new Set();
  }

  start() {
    this.wss = new WebSocketServer({
      port: this.port,
      verifyClient: this._verifyClient.bind(this),
    });

    this.wss.on("connection", this._onConnect.bind(this));
    this.wss.on("error", (err) => console.error("[WS] Server error:", err.message));

    console.log(`[WS] ✅ Dashboard WebSocket on port ${this.port}`);
  }

  // ── Auth ──────────────────────────────────────────────────────────────

  _verifyClient({ origin, req }, callback) {
    // Origin whitelist
    if (!this.allowedOrigins.includes(origin)) {
      console.warn(`[WS] Rejected origin: ${origin}`);
      return callback(false, 403, "Origin not allowed");
    }

    // JWT token from Authorization header
    const authHeader = req.headers["authorization"] || "";
    const token = authHeader.replace("Bearer ", "").trim();
    const clientIp = req.socket.remoteAddress;

    if (token) {
      const userId = this.jwt.verify(token, clientIp);
      if (!userId) {
        console.warn(`[WS] Rejected: invalid token from ${clientIp}`);
        return callback(false, 401, "Invalid token");
      }
      req.userId = userId;
    }
    // Allow unauthenticated for dashboard (read-only)
    // Uncomment below to require auth:
    // else { return callback(false, 401, "Token required"); }

    callback(true);
  }

  _onConnect(ws, req) {
    const clientIp = req.socket.remoteAddress;
    const clientId = `ws_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    ws._clientId = clientId;
    ws._ip = clientIp;

    this.clients.add(ws);
    console.log(`[WS] Client connected: ${clientId} (${clientIp}) | Total: ${this.clients.size}`);

    // Send welcome with current stats
    this._send(ws, { type: "connected", clientId, ts: Date.now() });

    ws.on("message", (data) => this._onMessage(ws, data));
    ws.on("close", () => {
      this.clients.delete(ws);
      console.log(`[WS] Client disconnected: ${clientId} | Remaining: ${this.clients.size}`);
    });
    ws.on("error", (err) => {
      console.error(`[WS] Client error (${clientId}):`, err.message);
      this.clients.delete(ws);
    });
  }

  _onMessage(ws, data) {
    // Rate limiting
    if (!this.rateLimiter.isAllowed(ws._clientId)) {
      this._send(ws, { type: "error", message: "Rate limit exceeded" });
      ws.close();
      return;
    }

    try {
      const msg = JSON.parse(data.toString());
      const type = sanitizeString(msg.type || "", 50);

      if (type === "ping") {
        this._send(ws, { type: "pong", ts: Date.now() });
      }
      // Future: handle admin commands here
    } catch {
      // Ignore malformed messages
    }
  }

  // ── Broadcasting ──────────────────────────────────────────────────────

  broadcast(payload) {
    /**
     * Send to ALL connected dashboard clients.
     * Used for: new bookings, call events, stats updates.
     */
    const message = JSON.stringify({ ...payload, ts: Date.now() });
    let sent = 0;
    for (const ws of this.clients) {
      if (ws.readyState === 1) { // OPEN
        ws.send(message);
        sent++;
      }
    }
    return sent;
  }

  broadcastNewBooking(booking) {
    return this.broadcast({ type: "new_booking", data: booking });
  }

  broadcastCallEvent(event) {
    return this.broadcast({ type: "call_event", data: event });
  }

  broadcastStats(stats) {
    return this.broadcast({ type: "stats_update", data: stats });
  }

  _send(ws, payload) {
    if (ws.readyState === 1) {
      ws.send(JSON.stringify(payload));
    }
  }

  getClientCount() {
    return this.clients.size;
  }
}
