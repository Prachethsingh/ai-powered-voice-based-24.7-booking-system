// components/BookingTable.jsx
import { useState } from "react";
import { RefreshCw, CheckCircle, Package } from "lucide-react";

const STATUS_COLORS = {
  pending:   "bg-yellow-900 text-yellow-300",
  confirmed: "bg-blue-900 text-blue-300",
  fulfilled: "bg-emerald-900 text-emerald-300",
  cancelled: "bg-red-900 text-red-300",
};

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
    <div className="bg-gray-900 rounded-xl border border-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <Package size={16} className="text-emerald-400" />
          All Bookings ({bookings.length})
        </h2>
        <button onClick={onRefresh}
          className="text-gray-400 hover:text-gray-200 transition-colors">
          <RefreshCw size={15} />
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500">
              <th className="text-left px-5 py-3">ID</th>
              <th className="text-left px-5 py-3">Phone</th>
              <th className="text-left px-5 py-3">Items</th>
              <th className="text-left px-5 py-3">Status</th>
              <th className="text-left px-5 py-3">Time</th>
              <th className="text-left px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {bookings.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-12 text-gray-600">
                  No bookings yet. Test with the input above.
                </td>
              </tr>
            )}
            {bookings.map((b) => (
              <tr key={b.id}
                className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-5 py-3 text-gray-500 font-mono">#{b.id}</td>
                <td className="px-5 py-3 font-mono text-emerald-400">{b.phone}</td>
                <td className="px-5 py-3 text-gray-300 max-w-xs truncate">
                  {Array.isArray(b.items) ? b.items.join(", ") : b.items}
                </td>
                <td className="px-5 py-3">
                  <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[b.status] || "bg-gray-700 text-gray-400"}`}>
                    {b.status}
                  </span>
                </td>
                <td className="px-5 py-3 text-gray-500 text-xs">
                  {b.created_at ? new Date(b.created_at * 1000).toLocaleString() : "—"}
                </td>
                <td className="px-5 py-3">
                  <div className="flex gap-2">
                    {b.status === "pending" && (
                      <button
                        onClick={() => updateStatus(b.id, "confirmed")}
                        disabled={updating === b.id}
                        className="text-xs bg-blue-900 hover:bg-blue-800 text-blue-300 px-2 py-1 rounded disabled:opacity-50"
                      >
                        Confirm
                      </button>
                    )}
                    {b.status === "confirmed" && (
                      <button
                        onClick={() => updateStatus(b.id, "fulfilled")}
                        disabled={updating === b.id}
                        className="text-xs bg-emerald-900 hover:bg-emerald-800 text-emerald-300 px-2 py-1 rounded disabled:opacity-50"
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
    </div>
  );
}
