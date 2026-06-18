// App.jsx — ai powered voice based 24.7 booking system Dashboard
import { useState, useEffect, useCallback } from "react";
import LiveDashboard from "./components/LiveDashboard.jsx";
import BookingTable from "./components/BookingTable.jsx";
import CallMetrics from "./components/CallMetrics.jsx";
import SecurityPanel from "./components/SecurityPanel.jsx";
import { Phone, BarChart3, Shield, List } from "lucide-react";

const WS_URL  = `ws://${window.location.hostname}:8080`;
const API_URL = `http://${window.location.hostname}:8000/api`;

const TABS = [
  { id: "live",     label: "Live Calls",  icon: Phone },
  { id: "bookings", label: "Bookings",    icon: List },
  { id: "metrics",  label: "Metrics",     icon: BarChart3 },
  { id: "security", label: "Security",    icon: Shield },
];

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

  // ── WebSocket ────────────────────────────────────────────────────────
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
        reconnectTimeout = setTimeout(connect, 3000); // Reconnect
      };

      ws.onerror = () => setWsStatus("error");
    };

    connect();

    // Keepalive ping
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

  // ── Fetch initial data ────────────────────────────────────────────────
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

  // ── Test Panel ────────────────────────────────────────────────────────
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

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Phone className="text-emerald-400" size={24} />
          <h1 className="text-xl font-bold tracking-tight">ai powered voice based 24.7 booking system</h1>
          <span className="text-xs bg-emerald-900 text-emerald-300 px-2 py-0.5 rounded-full">
            CPU-Only · LangChain · SmolLM 335M
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${
            wsStatus === "connected" ? "bg-emerald-400" :
            wsStatus === "connecting" ? "bg-yellow-400" : "bg-red-400"
          }`} />
          <span className="text-xs text-gray-400">{wsStatus}</span>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex gap-8">
        {[
          { label: "Total Bookings", value: stats.total_bookings },
          { label: "Today",          value: stats.today_bookings },
          { label: "Customers",      value: stats.total_users },
          { label: "Pending",        value: stats.pending },
          { label: "Live Calls",     value: liveCalls.length },
        ].map(({ label, value }) => (
          <div key={label} className="text-center">
            <div className="text-2xl font-bold text-emerald-400">{value}</div>
            <div className="text-xs text-gray-400">{label}</div>
          </div>
        ))}
      </div>

      {/* Test Panel */}
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-3">
        <div className="flex gap-3 items-start max-w-3xl">
          <div className="flex-1">
            <input
              type="text"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500"
              placeholder='Test pipeline: "I want rice and milk, my number is 9876543210"'
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTest()}
            />
          </div>
          <button
            onClick={handleTest}
            disabled={testLoading}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded text-sm font-medium"
          >
            {testLoading ? "Processing..." : "Test"}
          </button>
          {testResult && (
            <div className={`text-xs px-3 py-2 rounded border ${
              testResult.status === "success"
                ? "bg-emerald-950 border-emerald-700 text-emerald-300"
                : "bg-red-950 border-red-700 text-red-300"
            }`}>
              <strong>{testResult.status}</strong>
              {testResult.phone && <span> | 📱 {testResult.phone}</span>}
              {testResult.items?.length > 0 && (
                <span> | 🛒 {testResult.items.join(", ")}</span>
              )}
              {testResult.latency?.total_ms && (
                <span> | ⚡ {Math.round(testResult.latency.total_ms)}ms</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-800 px-6">
        <nav className="flex gap-0">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === id
                  ? "border-emerald-400 text-emerald-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <main className="p-6">
        {tab === "live"     && <LiveDashboard liveCalls={liveCalls} latestBookings={bookings.slice(0, 5)} />}
        {tab === "bookings" && <BookingTable  bookings={bookings} onRefresh={fetchBookings} apiUrl={API_URL} />}
        {tab === "metrics"  && <CallMetrics   stats={stats} bookings={bookings} />}
        {tab === "security" && <SecurityPanel events={securityEvents} />}
      </main>
    </div>
  );
}
