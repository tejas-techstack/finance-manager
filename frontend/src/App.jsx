import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./App.css";

const API = "http://127.0.0.1:8000";

const money = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

function App() {
  const [summary, setSummary] = useState([]);
  const [merchants, setMerchants] = useState([]);
  const [monthly, setMonthly] = useState([]);
  const [txns, setTxns] = useState([]);
  const [query, setQuery] = useState("");
  const [account, setAccount] = useState("");
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);

  const load = async () => {
    try {
      setError("");
      const [s, m, mo] = await Promise.all([
        axios.get(`${API}/summary`),
        axios.get(`${API}/merchants`),
        axios.get(`${API}/monthly`),
      ]);
      setSummary(s.data);
      setMerchants(m.data);
      setMonthly(mo.data);
    } catch (e) {
      setError("Can't reach the API on :8000. Is run.py still running?");
    }
  };

  const loadTxns = async () => {
    try {
      const params = {};
      if (query) params.q = query;
      if (account) params.account = account;
      const t = await axios.get(`${API}/transactions`, { params });
      setTxns(t.data);
    } catch {
      /* handled by load() */
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Offline-guard tripwire: the API process exits itself the moment the machine
  // goes online, so once /health stops answering we lock the screen and drop all
  // data from memory — the browser must not keep showing numbers while online.
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        await axios.get(`${API}/health`, { timeout: 1500 });
      } catch {
        setLocked(true);
        setSummary([]);
        setMerchants([]);
        setMonthly([]);
        setTxns([]);
      }
    }, 2000);
    return () => clearInterval(id);
  }, []);

  if (locked) {
    return (
      <div className="lockout">
        <div className="lockout-box">
          <div className="lockout-icon">⛔</div>
          <h1>Session locked</h1>
          <p>
            The backend stopped responding — this happens when the offline guard
            detects a network connection and shuts everything down.
          </p>
          <p className="lockout-hint">
            Disconnect from all networks and run <code>python run.py</code> again.
          </p>
        </div>
      </div>
    );
  }

  useEffect(() => {
    const id = setTimeout(loadTxns, 250); // debounce search
    return () => clearTimeout(id);
  }, [query, account]);

  const totals = useMemo(() => {
    const spent = summary.reduce((a, r) => a + (r.spent || 0), 0);
    const received = summary.reduce((a, r) => a + (r.received || 0), 0);
    const count = summary.reduce((a, r) => a + (r.count || 0), 0);
    return { spent, received, net: received - spent, count };
  }, [summary]);

  const maxMonth = Math.max(1, ...monthly.map((m) => m.spent || 0));
  const empty = summary.length === 0 && !error;

  return (
    <div className="app">
      <header className="topbar">
        <h1>Finance Manager</h1>
        <span className="offline-pill">● offline</span>
      </header>

      {error && <div className="banner error">{error}</div>}
      {empty && (
        <div className="banner">
          No transactions yet. Drop statements in <code>data/inbox/</code> and
          re-run <code>python run.py</code>.
        </div>
      )}

      <section className="cards">
        <Card label="Total spent" value={money(totals.spent)} accent="out" />
        <Card label="Total received" value={money(totals.received)} accent="in" />
        <Card label="Net" value={money(totals.net)} accent={totals.net < 0 ? "out" : "in"} />
        <Card label="Transactions" value={totals.count} />
      </section>

      <div className="grid">
        <section className="panel">
          <h2>By account</h2>
          <table>
            <thead>
              <tr><th>Account</th><th>Spent</th><th>Received</th><th>#</th></tr>
            </thead>
            <tbody>
              {summary.map((r) => (
                <tr key={r.account}>
                  <td>{r.account}</td>
                  <td className="out">{money(r.spent)}</td>
                  <td className="in">{money(r.received)}</td>
                  <td className="dim">{r.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="panel">
          <h2>Monthly spend</h2>
          <div className="bars">
            {monthly.map((m) => (
              <div className="bar-row" key={m.month}>
                <span className="bar-label">{m.month}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${(m.spent / maxMonth) * 100}%` }} />
                </div>
                <span className="bar-value">{money(m.spent)}</span>
              </div>
            ))}
            {monthly.length === 0 && <p className="dim">No dated rows yet.</p>}
          </div>
        </section>
      </div>

      <section className="panel">
        <h2>Top merchants</h2>
        <table>
          <thead>
            <tr><th>Merchant</th><th>Spent</th><th>#</th></tr>
          </thead>
          <tbody>
            {merchants.map((m, i) => (
              <tr key={i}>
                <td>{m.merchant}</td>
                <td className="out">{money(m.spent)}</td>
                <td className="dim">{m.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Transactions</h2>
          <div className="filters">
            <select value={account} onChange={(e) => setAccount(e.target.value)}>
              <option value="">All accounts</option>
              {summary.map((r) => (
                <option key={r.account} value={r.account}>{r.account}</option>
              ))}
            </select>
            <input
              placeholder="Search merchant / description..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
        <table>
          <thead>
            <tr><th>Date</th><th>Account</th><th>Merchant</th><th>Description</th><th>Amount</th></tr>
          </thead>
          <tbody>
            {txns.map((t, i) => (
              <tr key={i}>
                <td className="dim">{t.date}</td>
                <td>{t.account}</td>
                <td>{t.merchant}</td>
                <td className="desc">{t.description}</td>
                <td className={t.amount < 0 ? "out" : "in"}>{money(t.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Card({ label, value, accent }) {
  return (
    <div className={`card ${accent || ""}`}>
      <div className="card-label">{label}</div>
      <div className="card-value">{value}</div>
    </div>
  );
}

export default App;
