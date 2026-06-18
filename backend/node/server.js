/**
 * server.js — ai powered voice based 24.7 booking system Node.js Backend
 *
 * Combines:
 *  - Express REST API (proxy to Python AI service)
 *  - Asterisk ARI handler (telephony)
 *  - WebSocket server (live dashboard)
 *
 * Run: node server.js
 */
import express from "express";
import cors from "cors";
import { createServer } from "http";
import { config } from "dotenv";
import axios from "axios";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

import { AsteriskHandler } from "./ari_handler.js";
import { DashboardWSServer } from "./websocket_server.js";
import { JWTHelper, RateLimiter, sanitizeString } from "./auth.js";

// ── Setup ──────────────────────────────────────────────────────────────────

config({ path: join(dirname(fileURLToPath(import.meta.url)), "../../.env") });

const PORT         = parseInt(process.env.NODE_SERVER_PORT  || "8000");
const WS_PORT      = parseInt(process.env.WEBSOCKET_PORT    || "8080");
const PYTHON_API   = `http://127.0.0.1:${process.env.PYTHON_API_PORT || 8001}`;
const WS_ORIGINS   = (process.env.ALLOWED_WEBSOCKET_ORIGINS || "http://localhost:3000").split(",");
const ARI_HOST     = process.env.ASTERISK_HOST || "127.0.0.1";
const ARI_PORT     = parseInt(process.env.ASTERISK_ARI_PORT || "8088");
const ARI_USER     = process.env.ASTERISK_ARI_USER || "asterisk";
const ARI_PASSWORD = process.env.ASTERISK_ARI_PASSWORD;
const WS_SECRET    = process.env.WS_JWT_SECRET || "change-me";

// ── Express App ────────────────────────────────────────────────────────────

const app = express();
app.use(cors({ origin: WS_ORIGINS }));
app.use(express.json({ limit: "10mb" }));

const apiRateLimiter = new RateLimiter(200, 60_000);
const jwtHelper      = new JWTHelper(WS_SECRET);

// Simple rate-limit middleware
app.use((req, res, next) => {
  const ip = req.ip || "unknown";
  if (!apiRateLimiter.isAllowed(ip)) {
    return res.status(429).json({ error: "Rate limit exceeded" });
  }
  next();
});

// ── WebSocket Server ───────────────────────────────────────────────────────

const wsServer = new DashboardWSServer({
  port: WS_PORT,
  jwtSecret: WS_SECRET,
  allowedOrigins: WS_ORIGINS,
});
wsServer.start();

// ── Asterisk ARI ───────────────────────────────────────────────────────────

let ariHandler = null;

async function startARI() {
  if (!ARI_PASSWORD) {
    console.warn("[ARI] ASTERISK_ARI_PASSWORD not set — ARI disabled (demo mode)");
    return;
  }
  try {
    ariHandler = new AsteriskHandler({
      host: ARI_HOST,
      port: ARI_PORT,
      user: ARI_USER,
      password: ARI_PASSWORD,
      onCallResult: (result) => {
        // Broadcast every call result to dashboard
        wsServer.broadcastNewBooking(result);
        // Periodic stats update
        fetchAndBroadcastStats();
      },
    });
    await ariHandler.connect();
  } catch (err) {
    console.error("[ARI] Connection failed:", err.message);
    console.warn("[ARI] Running without Asterisk. REST API still works.");
  }
}

// ── Stats Broadcast ────────────────────────────────────────────────────────

async function fetchAndBroadcastStats() {
  try {
    const res = await axios.get(`${PYTHON_API}/stats`, { timeout: 3000 });
    wsServer.broadcastStats(res.data);
  } catch {
    // Python service might not be running
  }
}

// Broadcast stats every 30 seconds
setInterval(fetchAndBroadcastStats, 30_000);

// ── REST API Routes ────────────────────────────────────────────────────────

// Health check
app.get("/health", (req, res) => {
   res.json({
     status: "ok",
     service: "ai-powered-voice-booking-node",
    uptime: process.uptime(),
    active_calls: ariHandler?.getActiveCallCount() ?? 0,
    dashboard_clients: wsServer.getClientCount(),
  });
});

// Proxy: Stats
app.get("/api/stats", async (req, res) => {
  try {
    const r = await axios.get(`${PYTHON_API}/stats`, { timeout: 5000 });
    res.json(r.data);
  } catch (err) {
    res.status(503).json({ error: "AI service unavailable", detail: err.message });
  }
});

// Proxy: Recent bookings
app.get("/api/bookings", async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || "20"), 100);
  try {
    const r = await axios.get(`${PYTHON_API}/bookings?limit=${limit}`, { timeout: 5000 });
    res.json(r.data);
  } catch (err) {
    res.status(503).json({ error: "AI service unavailable" });
  }
});

// Proxy: Process text (for testing without a phone call)
app.post("/api/process-text", async (req, res) => {
  const { text, call_id } = req.body;
  if (!text) return res.status(400).json({ error: "text is required" });

  const safeText   = sanitizeString(text, 500);
  const safeCallId = sanitizeString(call_id || `web_${Date.now()}`, 64);

  try {
    const r = await axios.post(`${PYTHON_API}/process-text`, {
      text: safeText,
      call_id: safeCallId,
    }, { timeout: 15_000 });

    // Broadcast to dashboard
    if (r.data.status === "success") {
      wsServer.broadcastNewBooking(r.data);
    }

    res.json(r.data);
  } catch (err) {
    res.status(503).json({ error: "AI service unavailable", detail: err.message });
  }
});

// Update booking status
app.put("/api/bookings/:id/status", async (req, res) => {
  const id = parseInt(req.params.id);
  const { status } = req.body;
  if (!id || !status) return res.status(400).json({ error: "id and status required" });

  try {
    const r = await axios.put(`${PYTHON_API}/bookings/${id}/status`,
      { status }, { timeout: 5000 });
    res.json(r.data);
  } catch (err) {
    res.status(503).json({ error: "AI service unavailable" });
  }
});

// Generate dashboard JWT token
app.post("/api/auth/token", (req, res) => {
  const { user_id } = req.body;
  const ip = req.ip || "127.0.0.1";
  const token = jwtHelper.generate(user_id || "agent", ip);
  res.json({ token, expires_in: 3600 });
});

// ── Start Server ───────────────────────────────────────────────────────────

const server = createServer(app);

server.listen(PORT, "0.0.0.0", async () => {
   console.log("╔══════════════════════════════════════╗");
   console.log("║   ai powered voice based 24.7 booking system — Node.js Server   ║");
   console.log(`║   HTTP  : http://0.0.0.0:${PORT}       ║`);
   console.log(`║   WS    : ws://0.0.0.0:${WS_PORT}      ║`);
   console.log(`║   Python: ${PYTHON_API}  ║`);
   console.log("╚══════════════════════════════════════╝");

  await startARI();
  await fetchAndBroadcastStats();
});

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("[Server] SIGTERM: shutting down...");
  server.close(() => process.exit(0));
});
