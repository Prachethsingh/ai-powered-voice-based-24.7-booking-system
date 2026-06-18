import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Activity } from "lucide-react";

function StatCard({ label, value, sub, color = "text-emerald-300" }) {
  return (
    <div className="selene-card rounded-3xl border border-slate-800/80 p-5">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="mt-1 text-sm text-slate-400">{label}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-600">{sub}</div>}
    </div>
  );
}

function ChartPanel({ title, children }) {
  return (
    <section className="selene-card rounded-3xl border border-slate-800/80 p-5">
      <h2 className="mb-5 text-sm font-semibold text-white">{title}</h2>
      {children}
    </section>
  );
}

export default function CallMetrics({ stats, bookings }) {
  const hourlyData = Array.from({ length: 24 }, (_, h) => ({
    hour: `${h}:00`,
    orders: bookings.filter((b) => {
      if (!b.created_at) return false;
      return new Date(b.created_at * 1000).getHours() === h;
    }).length,
  }));

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
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total Bookings" value={stats.total_bookings} />
        <StatCard label="Today" value={stats.today_bookings} sub="last 24h" />
        <StatCard label="Customers" value={stats.total_users} sub="unique phones" />
        <StatCard label="Pending Orders" value={stats.pending} color={stats.pending > 10 ? "text-yellow-300" : "text-emerald-300"} />
      </div>

      <ChartPanel title="Orders by Hour">
        <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
          <Activity size={14} className="text-emerald-300" />
          Today
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={hourlyData}>
            <XAxis dataKey="hour" tick={{ fill: "#64748b", fontSize: 10 }} interval={3} />
            <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: 14 }}
              labelStyle={{ color: "#cbd5e1" }}
              itemStyle={{ color: "#5eead4" }}
            />
            <Bar dataKey="orders" fill="url(#seleneGradient)" radius={[8, 8, 0, 0]} />
            <defs>
              <linearGradient id="seleneGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#10b981" stopOpacity={0.65} />
              </linearGradient>
            </defs>
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>

      <ChartPanel title="Order Status Distribution">
        <div className="flex flex-wrap gap-3">
          {statusData.map(({ status, count }) => {
            const colors = {
              pending: "border-yellow-400/25 bg-yellow-400/10 text-yellow-200",
              confirmed: "border-blue-400/25 bg-blue-400/10 text-blue-200",
              fulfilled: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
              cancelled: "border-rose-400/25 bg-rose-400/10 text-rose-200",
            };
            return (
              <div key={status} className={`rounded-2xl border px-5 py-4 text-center min-w-[120px] ${colors[status] || "border-slate-700 bg-slate-800 text-slate-300"}`}>
                <div className="text-2xl font-bold">{count}</div>
                <div className="mt-1 text-xs capitalize">{status}</div>
              </div>
            );
          })}
          {statusData.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-800 px-5 py-4 text-sm text-slate-600">No data yet</div>
          )}
        </div>
      </ChartPanel>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: "STT (Whisper tiny.en)", target: "<500ms", model: "75MB Q4" },
          { label: "Intent (SmolLM 335M)", target: "<300ms", model: "200MB Q4" },
          { label: "Total E2E", target: "<2000ms", model: "CPU only" },
        ].map(({ label, target, model }) => (
          <div key={label} className="selene-card rounded-3xl border border-slate-800/80 p-5">
            <div className="text-xs text-slate-500">{label}</div>
            <div className="selene-gradient-text mt-2 text-2xl font-bold">{target}</div>
            <div className="mt-1 text-xs text-slate-600">{model}</div>
          </div>
        ))}
      </section>
    </div>
  );
}
