/**
 * auth.js — JWT + Rate Limiting for Node.js server
 * Protects WebSocket connections and ARI API calls.
 */
import crypto from "crypto";

// ── JWT (Lightweight, No Library) ─────────────────────────────────────────

export class JWTHelper {
  constructor(secret, ttlSeconds = 3600) {
    this.secret = Buffer.from(secret, "utf8");
    this.ttl = ttlSeconds;
  }

  generate(userId, ip) {
    const ts = Math.floor(Date.now() / 1000);
    const payload = `${userId}:${ip}:${ts}`;
    const mac = crypto
      .createHmac("sha256", this.secret)
      .update(payload)
      .digest("hex");
    return `${payload}.${mac}`;
  }

  verify(token, ip) {
    try {
      const lastDot = token.lastIndexOf(".");
      const payload = token.substring(0, lastDot);
      const mac = token.substring(lastDot + 1);

      const expected = crypto
        .createHmac("sha256", this.secret)
        .update(payload)
        .digest("hex");

      // Constant-time compare
      if (!crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(expected))) {
        return null;
      }

      const parts = payload.split(":");
      const ts = parseInt(parts[2], 10);
      const tokenIp = parts[1];

      if (tokenIp !== ip) return null; // IP mismatch
      if (Date.now() / 1000 - ts > this.ttl) return null; // Expired

      return parts[0]; // userId
    } catch {
      return null;
    }
  }
}

// ── Rate Limiter ───────────────────────────────────────────────────────────

export class RateLimiter {
  constructor(maxPerWindow = 100, windowMs = 60_000) {
    this.max = maxPerWindow;
    this.window = windowMs;
    this.store = new Map();
  }

  isAllowed(key) {
    const now = Date.now();
    const windowKey = `${key}:${Math.floor(now / this.window)}`;

    if (!this.store.has(windowKey)) {
      this.store.set(windowKey, 0);
      // Auto-cleanup old windows
      setTimeout(() => this.store.delete(windowKey), this.window * 2);
    }

    const count = this.store.get(windowKey) + 1;
    this.store.set(windowKey, count);
    return count <= this.max;
  }
}

// ── IP Whitelist ───────────────────────────────────────────────────────────

export function checkIpWhitelist(ip, allowedIPs) {
  if (!allowedIPs || allowedIPs.length === 0) return true;
  return allowedIPs.includes(ip);
}

// ── Input Sanitizer ────────────────────────────────────────────────────────

export function sanitizeString(input, maxLength = 500) {
  if (typeof input !== "string") return "";
  return input
    .substring(0, maxLength)
    .replace(/[<>"'`]/g, "")
    .replace(/javascript:/gi, "")
    .replace(/on\w+\s*=/gi, "");
}

export function validateCallId(callId) {
  return /^[a-zA-Z0-9\-_]{1,64}$/.test(callId);
}
