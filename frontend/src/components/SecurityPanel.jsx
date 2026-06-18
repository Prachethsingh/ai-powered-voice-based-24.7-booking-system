import { Shield, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

const EVENT_STYLES = {
  BOOKING_CREATED:   { color: "text-emerald-300", icon: CheckCircle,   bg: "border-emerald-400/20 bg-emerald-400/10" },
  BOOKING_DUPLICATE: { color: "text-yellow-300",  icon: AlertTriangle, bg: "border-yellow-400/20 bg-yellow-400/10" },
  RATE_LIMITED:      { color: "text-orange-300",  icon: AlertTriangle, bg: "border-orange-400/20 bg-orange-400/10" },
  RTP_TAMPER:        { color: "text-rose-300",    icon: XCircle,       bg: "border-rose-400/20 bg-rose-400/10" },
  AUTH_FAILED:       { color: "text-rose-300",    icon: XCircle,       bg: "border-rose-400/20 bg-rose-400/10" },
  PHONE_INVALID:     { color: "text-yellow-300",  icon: AlertTriangle, bg: "border-yellow-400/20 bg-yellow-400/10" },
};

const DEFAULT_STYLE = { color: "text-slate-400", icon: Shield, bg: "border-slate-700 bg-slate-800/60" };

function SummaryCard({ label, key, events, color }) {
  const count = events.filter((e) => e.event === key).length;

  return (
    <div className="selene-card rounded-3xl border border-slate-800/80 p-5 text-center">
      <div className={`text-3xl font-bold ${count > 0 ? color : "text-slate-600"}`}>{count}</div>
      <div className="mt-1 text-xs text-slate-500">{label}</div>
    </div>
  );
}

export default function SecurityPanel({ events }) {
  const securityAlerts = events.filter((e) =>
    ["RTP_TAMPER", "AUTH_FAILED", "RATE_LIMITED"].includes(e.event)
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <SummaryCard label="RTP Tampering" key="RTP_TAMPER" events={events} color="text-rose-300" />
        <SummaryCard label="Auth Failures" key="AUTH_FAILED" events={events} color="text-rose-300" />
        <SummaryCard label="Rate Limited" key="RATE_LIMITED" events={events} color="text-orange-300" />
      </div>

      <section className="selene-card rounded-3xl border border-slate-800/80 p-5">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10">
            <Shield size={18} className="text-emerald-300" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">Active Security Controls</h2>
            <p className="text-xs text-slate-500">Security-first runtime posture</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
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
            <div key={item} className="flex items-start gap-3 rounded-2xl border border-slate-800/70 bg-slate-950/35 p-3 text-xs text-slate-400">
              <CheckCircle size={13} className="mt-0.5 text-emerald-300 flex-shrink-0" />
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="selene-card overflow-hidden rounded-3xl border border-slate-800/80">
        <div className="border-b border-slate-800/80 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Security Event Log</h2>
              <p className="mt-1 text-xs text-slate-500">{events.length} events captured</p>
            </div>
            {securityAlerts.length > 0 && (
              <span className="rounded-full border border-rose-400/25 bg-rose-400/10 px-3 py-1 text-xs font-semibold text-rose-200">
                {securityAlerts.length} alerts
              </span>
            )}
          </div>
        </div>
        <div className="divide-y divide-slate-800/70 max-h-96 overflow-y-auto">
          {events.length === 0 && (
            <div className="py-14 text-center text-sm text-slate-600">
              No security events recorded
            </div>
          )}
          {events.map((e, i) => {
            const style = EVENT_STYLES[e.event] || DEFAULT_STYLE;
            const Icon = style.icon;
            return (
              <div key={i} className={`flex items-start gap-3 border-l-4 px-5 py-4 ${style.bg}`}>
                <Icon size={15} className={`${style.color} mt-0.5 flex-shrink-0`} />
                <div className="min-w-0 flex-1">
                  <div className={`text-xs font-mono font-semibold ${style.color}`}>{e.event}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {e.call_id !== "N/A" && <span>Call: {e.call_id} · </span>}
                    {e.phone_hash !== "N/A" && (
                      <span title="SHA-256 hash (non-reversible)">
                        Hash: {e.phone_hash?.slice(0, 12)}… ·{" "}
                      </span>
                    )}
                    {e.ts && new Date(e.ts * 1000).toLocaleTimeString()}
                  </div>
                </div>
                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
                  e.status === "OK" ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" :
                  e.status === "SECURITY_ALERT" ? "border-rose-400/25 bg-rose-400/10 text-rose-200" :
                  "border-slate-700 bg-slate-800 text-slate-300"
                }`}>
                  {e.status}
                </span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
