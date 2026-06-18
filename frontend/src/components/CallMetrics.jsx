// components/CallMetrics.jsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import { Activity } from "lucide-react";

function StatCard({ label, value, sub, color = "text-emerald-400" }) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-sm text-gray-400 mt-1">{label}</div>
      {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function CallMetrics({ stats, bookings }) {
  // Build hourly chart from bookings
  const hourlyData = Array.from({ length: 24 }, (_, h) => ({
    hour: `${h}:00`,
    orders: bookings.filter((b) => {
      if (!b.created_at) return false;
      return new Date(b.created_at * 1000).getHours() === h;
    }).length,
  }));

  // Status distribution
  const statusCounts = bookings.reduce((acc, b) => {
    acc[b.status] = (acc[b.status] || 0) + 1;
    return acc;
  }, {});
  const statusData = Object.entries(statusCounts).map(([status, count]) => ({
    status,
    count,
  }));

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Bookings"  value={stats.total_bookings} />
        <StatCard label="Today"           value={stats.today_bookings} sub="last 24h" />
        <StatCard label="Customers"       value={stats.total_users} sub="unique phones" />
        <StatCard label="Pending Orders"  value={stats.pending}
          color={stats.pending > 10 ? "text-yellow-400" : "text-emerald-400"} />
      </div>

      {/* Hourly chart */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <Activity size={16} className="text-emerald-400" />
          Orders by Hour (Today)
        </h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={hourlyData}>
            <XAxis dataKey="hour" tick={{ fill: "#6b7280", fontSize: 10 }}
              interval={3} />
            <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
              labelStyle={{ color: "#9ca3af" }}
              itemStyle={{ color: "#34d399" }}
            />
            <Bar dataKey="orders" fill="#059669" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Status distribution */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">Order Status Distribution</h2>
        <div className="flex gap-4 flex-wrap">
          {statusData.map(({ status, count }) => {
            const colors = {
              pending:   "bg-yellow-900 text-yellow-300 border-yellow-800",
              confirmed: "bg-blue-900 text-blue-300 border-blue-800",
              fulfilled: "bg-emerald-900 text-emerald-300 border-emerald-800",
              cancelled: "bg-red-900 text-red-300 border-red-800",
            };
            return (
              <div key={status}
                className={`px-4 py-3 rounded-lg border text-center min-w-[100px] ${colors[status] || "bg-gray-800 text-gray-400 border-gray-700"}`}>
                <div className="text-2xl font-bold">{count}</div>
                <div className="text-xs mt-1 capitalize">{status}</div>
              </div>
            );
          })}
          {statusData.length === 0 && (
            <div className="text-gray-600 text-sm py-4">No data yet</div>
          )}
        </div>
      </div>

      {/* Performance info */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">Pipeline Performance (Targets)</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          {[
            { label: "STT (Whisper tiny.en)", target: "<500ms", model: "75MB Q4" },
            { label: "Intent (SmolLM 335M)", target: "<300ms", model: "200MB Q4" },
            { label: "Total E2E",            target: "<2000ms", model: "CPU only" },
          ].map(({ label, target, model }) => (
            <div key={label} className="bg-gray-800 rounded-lg p-4">
              <div className="text-gray-400 text-xs">{label}</div>
              <div className="text-emerald-400 text-xl font-bold mt-1">{target}</div>
              <div className="text-gray-600 text-xs mt-1">{model}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
