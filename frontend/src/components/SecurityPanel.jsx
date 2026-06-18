// components/SecurityPanel.jsx
import { Shield, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

const EVENT_STYLES = {
  BOOKING_CREATED:   { color: "text-emerald-400", icon: CheckCircle,   bg: "bg-emerald-950 border-emerald-900" },
  BOOKING_DUPLICATE: { color: "text-yellow-400",  icon: AlertTriangle, bg: "bg-yellow-950 border-yellow-900" },
  RATE_LIMITED:      { color: "text-orange-400",  icon: AlertTriangle, bg: "bg-orange-950 border-orange-900" },
  RTP_TAMPER:        { color: "text-red-400",      icon: XCircle,       bg: "bg-red-950 border-red-900" },
  AUTH_FAILED:       { color: "text-red-400",      icon: XCircle,       bg: "bg-red-950 border-red-900" },
  PHONE_INVALID:     { color: "text-yellow-400",  icon: AlertTriangle, bg: "bg-yellow-950 border-yellow-900" },
};

const DEFAULT_STYLE = { color: "text-gray-400", icon: Shield, bg: "bg-gray-800 border-gray-700" };

export default function SecurityPanel({ events }) {
  const securityAlerts = events.filter((e) =>
    ["RTP_TAMPER", "AUTH_FAILED", "RATE_LIMITED"].includes(e.event)
  );

  return (
    <div className="space-y-6">
      {/* Alert Summary */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "RTP Tampering",   key: "RTP_TAMPER",  color: "text-red-400" },
          { label: "Auth Failures",   key: "AUTH_FAILED", color: "text-red-400" },
          { label: "Rate Limited",    key: "RATE_LIMITED",color: "text-orange-400" },
        ].map(({ label, key, color }) => {
          const count = events.filter((e) => e.event === key).length;
          return (
            <div key={key} className="bg-gray-900 rounded-xl border border-gray-800 p-5 text-center">
              <div className={`text-3xl font-bold ${count > 0 ? color : "text-gray-600"}`}>
                {count}
              </div>
              <div className="text-xs text-gray-400 mt-1">{label}</div>
            </div>
          );
        })}
      </div>

      {/* Security Features Active */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <Shield size={16} className="text-emerald-400" />
          Active Security Controls
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            "Phone numbers encrypted (AES-128-CBC Fernet)",
            "SQL injection protected (parameterized queries only)",
            "Rate limiting: 5 bookings/hour per phone",
            "Deduplication: 5-minute Redis window",
            "RTP packets HMAC-SHA256 signed",
            "WebSocket: JWT auth + origin whitelist",
            "ARI API: JWT auth + IP whitelist",
            "Audit log: phone hash only (non-reversible SHA-256)",
          ].map((item) => (
            <div key={item} className="flex items-start gap-2 text-xs text-gray-400">
              <CheckCircle size={12} className="text-emerald-400 mt-0.5 flex-shrink-0" />
              {item}
            </div>
          ))}
        </div>
      </div>

      {/* Event Log */}
      <div className="bg-gray-900 rounded-xl border border-gray-800">
        <div className="px-5 py-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-gray-300">
            Security Event Log ({events.length})
          </h2>
        </div>
        <div className="divide-y divide-gray-800 max-h-96 overflow-y-auto">
          {events.length === 0 && (
            <div className="text-center py-12 text-gray-600 text-sm">
              No security events recorded
            </div>
          )}
          {events.map((e, i) => {
            const style = EVENT_STYLES[e.event] || DEFAULT_STYLE;
            const Icon  = style.icon;
            return (
              <div key={i} className={`flex items-start gap-3 px-5 py-3 border-l-2 ${style.bg} ${style.color.replace("text-", "border-")}`}>
                <Icon size={14} className={`${style.color} mt-0.5 flex-shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-mono font-semibold ${style.color}`}>{e.event}</div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {e.call_id !== "N/A" && <span>Call: {e.call_id} · </span>}
                    {e.phone_hash !== "N/A" && (
                      <span title="SHA-256 hash (non-reversible)">
                        Hash: {e.phone_hash?.slice(0, 12)}… ·{" "}
                      </span>
                    )}
                    {e.ts && new Date(e.ts * 1000).toLocaleTimeString()}
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  e.status === "OK" ? "bg-emerald-950 text-emerald-400" :
                  e.status === "SECURITY_ALERT" ? "bg-red-950 text-red-400" :
                  "bg-gray-800 text-gray-400"
                }`}>
                  {e.status}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
