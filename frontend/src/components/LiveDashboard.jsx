import { Phone, CheckCircle, Clock } from "lucide-react";

function StatusBadge({ status }) {
  const styles = {
    pending: "border-yellow-400/25 bg-yellow-400/10 text-yellow-200",
    confirmed: "border-blue-400/25 bg-blue-400/10 text-blue-200",
    fulfilled: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
    cancelled: "border-rose-400/25 bg-rose-400/10 text-rose-200",
  };

  return (
    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${styles[status] || "border-slate-700 bg-slate-800 text-slate-300"}`}>
      {status || "unknown"}
    </span>
  );
}

export default function LiveDashboard({ liveCalls, latestBookings }) {
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <section className="selene-card rounded-3xl border border-slate-800/80 p-5">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10">
              <Phone size={18} className="text-emerald-300" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Active Calls</h2>
              <p className="text-xs text-slate-500">Real-time call processing</p>
            </div>
          </div>
          <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
            {liveCalls.length}
          </span>
        </div>

        {liveCalls.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 text-center">
            <Phone size={30} className="mb-3 text-slate-700" />
            <p className="text-sm font-medium text-slate-300">No active calls right now</p>
            <p className="mt-1 text-xs text-slate-600">Incoming calls will appear here automatically.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {liveCalls.map((call) => (
              <div key={call.call_id} className="selene-card flex items-center gap-4 rounded-2xl border border-slate-800/80 p-4">
                <span className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-slate-100">{call.call_id}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <Clock size={12} />
                    Processing voice order
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="selene-card rounded-3xl border border-slate-800/80 p-5">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-400/10">
              <CheckCircle size={18} className="text-violet-300" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Latest Orders</h2>
              <p className="text-xs text-slate-500">Live booking feed</p>
            </div>
          </div>
        </div>

        {latestBookings.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 text-center">
            <CheckCircle size={30} className="mb-3 text-slate-700" />
            <p className="text-sm font-medium text-slate-300">No orders yet</p>
            <p className="mt-1 text-xs text-slate-600">Use the pipeline test or receive a call to populate this feed.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {latestBookings.map((b, i) => (
              <div key={b.id || i} className="selene-card rounded-2xl border border-slate-800/80 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-emerald-200">{b.phone}</div>
                    <div className="mt-1 break-words text-xs text-slate-400">
                      {Array.isArray(b.items) ? b.items.join(", ") : b.items}
                    </div>
                  </div>
                  <StatusBadge status={b.status} />
                </div>
                <div className="mt-3 text-xs text-slate-600">
                  {b.created_at ? new Date(b.created_at * 1000).toLocaleString() : "Time unavailable"}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
