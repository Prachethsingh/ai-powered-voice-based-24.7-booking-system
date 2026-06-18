import { useState } from "react";
import { RefreshCw, Package } from "lucide-react";

const STATUS_COLORS = {
  pending: "border-yellow-400/25 bg-yellow-400/10 text-yellow-200",
  confirmed: "border-blue-400/25 bg-blue-400/10 text-blue-200",
  fulfilled: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
  cancelled: "border-rose-400/25 bg-rose-400/10 text-rose-200",
};

function StatusBadge({ status }) {
  return (
    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_COLORS[status] || "border-slate-700 bg-slate-800 text-slate-300"}`}>
      {status || "unknown"}
    </span>
  );
}

export default function BookingTable({ bookings, onRefresh, apiUrl }) {
  const [updating, setUpdating] = useState(null);

  const updateStatus = async (id, status) => {
    setUpdating(id);
    try {
      await fetch(`${apiUrl}/bookings/${id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      onRefresh();
    } catch {}
    setUpdating(null);
  };

  return (
    <section className="selene-card overflow-hidden rounded-3xl border border-slate-800/80">
      <div className="flex flex-col gap-4 border-b border-slate-800/80 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-400/10">
            <Package size={18} className="text-violet-300" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">All Bookings</h2>
            <p className="text-xs text-slate-500">{bookings.length} records loaded</p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          className="inline-flex items-center justify-center rounded-full border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:border-violet-400/30 hover:text-white"
        >
          <RefreshCw size={14} className="mr-2" />
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-950/40 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-4 text-left">ID</th>
              <th className="px-5 py-4 text-left">Phone</th>
              <th className="px-5 py-4 text-left">Items</th>
              <th className="px-5 py-4 text-left">Status</th>
              <th className="px-5 py-4 text-left">Time</th>
              <th className="px-5 py-4 text-left">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {bookings.length === 0 && (
              <tr>
                <td colSpan={6} className="py-14 text-center text-sm text-slate-600">
                  No bookings yet. Test the pipeline above or receive a call.
                </td>
              </tr>
            )}
            {bookings.map((b) => (
              <tr key={b.id} className="transition hover:bg-slate-800/35">
                <td className="px-5 py-4 font-mono text-slate-500">#{b.id}</td>
                <td className="px-5 py-4 font-mono text-emerald-200">{b.phone}</td>
                <td className="px-5 py-4 max-w-xs truncate text-slate-300">
                  {Array.isArray(b.items) ? b.items.join(", ") : b.items}
                </td>
                <td className="px-5 py-4">
                  <StatusBadge status={b.status} />
                </td>
                <td className="px-5 py-4 text-xs text-slate-500">
                  {b.created_at ? new Date(b.created_at * 1000).toLocaleString() : "—"}
                </td>
                <td className="px-5 py-4">
                  <div className="flex gap-2">
                    {b.status === "pending" && (
                      <button
                        onClick={() => updateStatus(b.id, "confirmed")}
                        disabled={updating === b.id}
                        className="rounded-full bg-blue-400/10 px-3 py-1.5 text-xs font-semibold text-blue-200 transition hover:bg-blue-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Confirm
                      </button>
                    )}
                    {b.status === "confirmed" && (
                      <button
                        onClick={() => updateStatus(b.id, "fulfilled")}
                        disabled={updating === b.id}
                        className="rounded-full bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Fulfill
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
