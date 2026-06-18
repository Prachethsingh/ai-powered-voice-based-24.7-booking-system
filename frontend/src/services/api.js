// src/services/api.js — REST API client for dashboard
const BASE = `http://${window.location.hostname}:8000/api`;

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const api = {
  health:        ()           => req("/health"),  // Actually /health on node root
  stats:         ()           => req("/stats"),
  bookings:      (limit = 50) => req(`/bookings?limit=${limit}`),
  processText:   (text, callId) =>
    req("/process-text", {
      method: "POST",
      body: JSON.stringify({ text, call_id: callId }),
    }),
  updateStatus: (id, status) =>
    req(`/bookings/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),
  getToken: (userId = "agent") =>
    req("/auth/token", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
};
