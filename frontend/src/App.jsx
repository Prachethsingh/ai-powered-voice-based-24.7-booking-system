import { useState, useEffect, useCallback } from "react";
import LiveDashboard from "./components/LiveDashboard.jsx";
import BookingTable from "./components/BookingTable.jsx";
import CallMetrics from "./components/CallMetrics.jsx";
import SecurityPanel from "./components/SecurityPanel.jsx";
import { Phone, BarChart3, Shield, List, Moon, Sparkles } from "lucide-react";

const WS_URL  = `ws://${window.location.hostname}:8080`;
const API_URL = `http://${window.location.hostname}:8000/api`;

const TABS = [
  { id: "live",     label: "Live Calls",  icon: Phone },
  { id: "bookings", label: "Bookings",    icon: List },
  { id: "metrics",  label: "Metrics",     icon: BarChart3 },
  { id: "security", label: "Security",    icon: Shield },
];

const statusClass = (status) => {
  if (status === "connected") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-300";
  if (status === "connecting") return "border-amber-400/30 bg-amber-400/10 text-amber-300";
  return "border-rose-400/30 bg-rose-400/10 text-rose-300";
};

const statusDotClass = (status) => {
  if (status === "connected") return "bg-emerald-400 shadow-emerald-400/70";
  if (status === "connecting") return "bg-amber-400 shadow-amber-400/70";
  return "bg-rose-400 shadow-rose-400/70";
};

export default function App() {
  const [tab, setTab] = useState("live");
  const [bookings, setBookings] = useState([]);
  const [stats, setStats] = useState({ total_bookings: 0, today_bookings: 0, total_users: 0, pending: 0 });
  const [liveCalls, setLiveCalls] = useState([]);
  const [securityEvents, setSecurityEvents] = useState([]);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [testInput, setTestInput] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [testLoading, setTestLoading] = useState(false);

  useEffect(() => {
    let ws;
    let reconnectTimeout;

    const connect = () => {
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setWsStatus("connected");
        console.log("[WS] Connected");
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          handleWSMessage(msg);
        } catch {}
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = () => setWsStatus("error");
    };

    connect();

    const pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30_000);

    return () => {
      clearTimeout(reconnectTimeout);
      clearInterval(pingInterval);
      ws?.close();
    };
  }, []);

  const handleWSMessage = useCallback((msg) => {
    switch (msg.type) {
      case "new_booking":
        setBookings((prev) => [msg.data, ...prev].slice(0, 200));
        setLiveCalls((prev) => prev.filter((c) => c.call_id !== msg.data.call_id));
        break;
      case "stats_update":
        setStats(msg.data);
        break;
      case "call_event":
        if (msg.data.type === "started") {
          setLiveCalls((prev) => [...prev, msg.data]);
        } else if (msg.data.type === "ended") {
          setLiveCalls((prev) => prev.filter((c) => c.call_id !== msg.data.call_id));
        }
        break;
      case "security_event":
        setSecurityEvents((prev) => [msg.data, ...prev].slice(0, 100));
        break;
    }
  }, []);

  useEffect(() => {
    fetchBookings();
    fetchStats();
  }, []);

  const fetchBookings = async () => {
    try {
      const r = await fetch(`${API_URL}/bookings?limit=50`);
      const data = await r.json();
      setBookings(data.bookings || []);
    } catch {}
  };

  const fetchStats = async () => {
    try {
      const r = await fetch(`${API_URL}/stats`);
      const data = await r.json();
      setStats(data);
    } catch {}
  };

  const handleTest = async () => {
    if (!testInput.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const r = await fetch(`${API_URL}/process-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: testInput, call_id: `test_${Date.now()}` }),
      });
      const data = await r.json();
      setTestResult(data);
      if (data.status === "success") fetchBookings();
    } catch (err) {
      setTestResult({ status: "error", message: err.message });
    } finally {
      setTestLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-violet-400/30 selection:text-white">
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute left-[-12rem] top-[-10rem] h-96 w-96 rounded-full bg-violet-500/20 blur-3xl" />
        <div className="absolute right-[-10rem] top-[8rem] h-96 w-96 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="absolute bottom-[-12rem] left-[25%] h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
      </div>

      <header className="selene-glass sticky top-0 z-30 border-b border-slate-800/80 px-5 py-4 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-400/10 shadow-lg shadow-violet-950/40">
              <Moon className="text-violet-300" size={24} />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-white">FLY Platform</h1>
                <span className="selene-gradient-text rounded-full border border-violet-400/20 bg-violet-400/10 px-3 py-1 text-xs font-semibold">
                  Selene UI
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                AI-powered 24/7 voice booking console · CPU-only · LangChain · SmolLM 335M
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${statusClass(wsStatus)}`}>
              <span className={`mr-2 inline-block h-2 w-2 rounded-full shadow-sm ${statusDotClass(wsStatus)}`} />
              {wsStatus}
            </div>
            <div className="rounded-full border border-slate-700/70 bg-slate-900/70 px-3 py-1.5 text-xs text-slate-400">
              <Sparkles size={12} className="mr-1.5 inline text-violet-300" />
              24/7 voice booking
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-3 px-5 py-5 md:grid-cols-5">
        {[
          { label: "Total Bookings", value: stats.total_bookings },
          { label: "Today",          value: stats.today_bookings },
          { label: "Customers",      value: stats.total_users },
          { label: "Pending",        value: stats.pending },
          { label: "Live Calls",     value: liveCalls.length },
        ].map(({ label, value }) => (
          <div key={label} className="selene-card rounded-2xl border border-slate-800/80 p-4 text-center">
            <div className="selene-gradient-text text-2xl font-bold">{value}</div>
            <div className="mt-1 text-xs text-slate-500">{label}</div>
          </div>
        ))}
      </div>

      <section className="mx-auto max-w-7xl px-5">
        <div className="selene-glass rounded-3xl border border-slate-800/80 p-4 shadow-2xl shadow-violet-950/20">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="flex-1">
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Test AI pipeline
              </label>
              <input
                type="text"
                className="selene-input w-full rounded-2xl border border-slate-700/80 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 focus:border-violet-400 focus:outline-none focus:ring-4 focus:ring-violet-400/10"
                placeholder='Try: "I want rice and milk, my number is 9876543210"'
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleTest()}
              />
            </div>
            <button
              onClick={handleTest}
              disabled={testLoading}
              className="rounded-2xl bg-gradient-to-r from-violet-500 to-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-950/30 transition hover:scale-[1.01] hover:from-violet-400 hover:to-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {testLoading ? "Processing..." : "Run Test"}
            </button>
            {testResult && (
              <div className={`rounded-2xl border px-4 py-3 text-xs ${
                testResult.status === "success"
                  ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                  : "border-rose-400/30 bg-rose-400/10 text-rose-200"
              }`}>
                <strong>{testResult.status}</strong>
                {testResult.phone && <span> · {testResult.phone}</span>}
                {testResult.items?.length > 0 && <span> · {testResult.items.join(", ")}</span>}
                {testResult.latency?.total_ms && <span> · {Math.round(testResult.latency.total_ms)}ms</span>}
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-5 pt-5">
        <nav className="flex gap-2 overflow-x-auto pb-3">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex min-w-max items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold transition ${
                tab === id
                  ? "border-violet-400/30 bg-violet-400/15 text-white shadow-lg shadow-violet-950/20"
                  : "border-slate-800/80 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
      </div>

      <main className="mx-auto max-w-7xl p-5">
        {tab === "live"     && <LiveDashboard liveCalls={liveCalls} latestBookings={bookings.slice(0, 5)} />}
        {tab === "bookings" && <BookingTable  bookings={bookings} onRefresh={fetchBookings} apiUrl={API_URL} />}
        {tab === "metrics"  && <CallMetrics   stats={stats} bookings={bookings} />}
        {tab === "security" && <SecurityPanel events={securityEvents} />}
      </main>
    </div>
  );
}
