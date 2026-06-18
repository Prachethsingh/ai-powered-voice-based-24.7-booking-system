// components/LiveDashboard.jsx
import { Phone, CheckCircle, Clock, AlertCircle } from "lucide-react";

export default function LiveDashboard({ liveCalls, latestBookings }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Active Calls */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <Phone size={16} className="text-emerald-400" />
          Active Calls ({liveCalls.length})
        </h2>
        {liveCalls.length === 0 ? (
          <div className="text-center py-10 text-gray-600 text-sm">
            No active calls right now
          </div>
        ) : (
          <div className="space-y-3">
            {liveCalls.map((call) => (
              <div key={call.call_id}
                className="flex items-center gap-3 bg-gray-800 rounded-lg px-4 py-3 border border-gray-700">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <div className="flex-1">
                  <div className="text-sm font-mono text-gray-200">{call.call_id}</div>
                  <div className="text-xs text-gray-500">Processing...</div>
                </div>
                <Clock size={14} className="text-gray-500" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Latest Bookings (live feed) */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <CheckCircle size={16} className="text-emerald-400" />
          Latest Orders (Live)
        </h2>
        {latestBookings.length === 0 ? (
          <div className="text-center py-10 text-gray-600 text-sm">
            No orders yet
          </div>
        ) : (
          <div className="space-y-3">
            {latestBookings.map((b, i) => (
              <div key={b.id || i}
                className="bg-gray-800 rounded-lg px-4 py-3 border border-gray-700">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-sm font-mono text-emerald-400">{b.phone}</div>
                    <div className="text-xs text-gray-300 mt-1">
                      {Array.isArray(b.items) ? b.items.join(", ") : b.items}
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    b.status === "confirmed" ? "bg-emerald-900 text-emerald-300" :
                    b.status === "pending"   ? "bg-yellow-900 text-yellow-300" :
                    "bg-gray-700 text-gray-400"
                  }`}>
                    {b.status}
                  </span>
                </div>
                <div className="text-xs text-gray-600 mt-1">
                  {b.created_at ? new Date(b.created_at * 1000).toLocaleTimeString() : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
