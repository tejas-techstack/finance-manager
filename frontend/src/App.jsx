import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./App.css";

const API = "http://127.0.0.1:8000";
const INR = (n, dp = 2) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: dp });

const EMPTY = { q: "", account: "", type: "all", from: "", to: "", min: "", max: "", merchant: "" };

const debitOf = (r) => (r.amount < 0 ? -r.amount : 0);
const creditOf = (r) => (r.amount > 0 ? r.amount : 0);

export default function App() {
  const [all, setAll] = useState([]);
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState(EMPTY);
  const [sort, setSort] = useState({ key: "date", dir: "desc" });
  const [mSort, setMSort] = useState({ key: "debit", dir: "desc" });
  const setFilter = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = async () => {
    try {
      setError("");
      const res = await axios.get(`${API}/transactions`, { params: { limit: 100000 } });
      setAll(res.data);
    } catch {
      setError("Can't reach the API on :8000 — is run.py still running?");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  // offline-guard tripwire: API exits when the machine goes online -> lock + wipe
  useEffect(() => {
    const id = setInterval(async () => {
      try { await axios.get(`${API}/health`, { timeout: 1500 }); }
      catch { setLocked(true); setAll([]); }
    }, 2000);
    return () => clearInterval(id);
  }, []);

  // --- derived data (all client-side, memoised) ---
  const base = useMemo(() => all.filter((r) => {
    if (f.account && r.account !== f.account) return false;
    if (f.type === "debit" && !(r.amount < 0)) return false;
    if (f.type === "credit" && !(r.amount > 0)) return false;
    if (f.from && r.date < f.from) return false;
    if (f.to && r.date > f.to) return false;
    const mag = Math.abs(r.amount || 0);
    if (f.min !== "" && mag < parseFloat(f.min)) return false;
    if (f.max !== "" && mag > parseFloat(f.max)) return false;
    if (f.q && !`${r.merchant} ${r.description}`.toLowerCase().includes(f.q.toLowerCase()))
      return false;
    return true;
  }), [all, f.account, f.type, f.from, f.to, f.min, f.max, f.q]);

  // merchant filter applies to everything EXCEPT the merchant list (so you can still switch)
  const rows = useMemo(
    () => (f.merchant ? base.filter((r) => r.merchant === f.merchant) : base),
    [base, f.merchant],
  );

  const sorted = useMemo(() => {
    const val = {
      date: (r) => r.date, account: (r) => r.account, merchant: (r) => r.merchant,
      description: (r) => r.description, debit: (r) => debitOf(r), credit: (r) => creditOf(r),
      balance: (r) => (r.balance == null ? -Infinity : r.balance),
    }[sort.key];
    const arr = [...rows].sort((a, b) => {
      const va = val(a), vb = val(b);
      return va < vb ? -1 : va > vb ? 1 : 0;
    });
    return sort.dir === "desc" ? arr.reverse() : arr;
  }, [rows, sort]);

  const kpi = useMemo(() => {
    let spent = 0, received = 0, largest = 0, largestCr = 0, nDeb = 0;
    for (const r of rows) {
      const d = debitOf(r), c = creditOf(r);
      spent += d; received += c;
      if (d > largest) largest = d;
      if (c > largestCr) largestCr = c;
      if (r.amount < 0) nDeb++;
    }
    return { spent, received, net: received - spent, count: rows.length,
             largest, largestCr, avg: nDeb ? spent / nDeb : 0 };
  }, [rows]);

  const byAccount = useMemo(() => {
    const m = {};
    for (const r of rows) {
      const a = (m[r.account] ||= { account: r.account, spent: 0, received: 0, count: 0 });
      a.spent += debitOf(r); a.received += creditOf(r); a.count++;
    }
    return Object.values(m).sort((x, y) => y.spent - x.spent);
  }, [rows]);

  const monthly = useMemo(() => {
    const m = {};
    for (const r of rows) {
      if (!r.date || r.date.length < 7) continue;
      const o = (m[r.date.slice(0, 7)] ||= { month: r.date.slice(0, 7), spent: 0, received: 0 });
      o.spent += debitOf(r); o.received += creditOf(r);
    }
    return Object.values(m).sort((a, b) => (a.month < b.month ? -1 : 1));
  }, [rows]);

  const merchants = useMemo(() => {
    const m = {};
    for (const r of base) {
      const o = (m[r.merchant] ||= { merchant: r.merchant, spent: 0, received: 0, count: 0 });
      o.spent += debitOf(r); o.received += creditOf(r); o.count++;
    }
    const arr = Object.values(m).map((o) => ({ ...o, net: o.received - o.spent }));
    const val = {
      merchant: (x) => x.merchant, count: (x) => x.count,
      debit: (x) => x.spent, credit: (x) => x.received, net: (x) => x.net,
    }[mSort.key];
    arr.sort((a, b) => { const va = val(a), vb = val(b); return va < vb ? -1 : va > vb ? 1 : 0; });
    return mSort.dir === "desc" ? arr.reverse() : arr;
  }, [base, mSort]);

  const accounts = useMemo(() => [...new Set(all.map((r) => r.account))].sort(), [all]);
  const dateRange = useMemo(() => {
    const ds = rows.map((r) => r.date).filter(Boolean).sort();
    return ds.length ? `${ds[0]} → ${ds[ds.length - 1]}` : "—";
  }, [rows]);
  const acctColor = (name) => `var(--cat-${(accounts.indexOf(name) % 8) + 1})`;

  if (locked) return <Lock />;

  const maxMonth = Math.max(1, ...monthly.flatMap((m) => [m.spent, m.received]));
  const active = f.q || f.account || f.type !== "all" || f.from || f.to || f.min || f.max || f.merchant;
  const CAP = 400;

  return (
    <div className="app">
      <header className="topbar">
        <h1>Finance Manager</h1>
        <span className="pill">● offline</span>
        <span className="spacer" />
        <span className="muted">{all.length.toLocaleString("en-IN")} transactions</span>
        <button className="btn" onClick={load}>Refresh</button>
      </header>

      {error && <div className="banner error">{error}</div>}
      {!error && !loading && all.length === 0 && (
        <div className="banner">
          No transactions. Add statements to <code>data/inbox/</code> and re-run <code>python run.py</code>.
        </div>
      )}

      {/* KPI cards reflect the current filters */}
      <section className="cards">
        <Card label="Spent" value={INR(kpi.spent)} tone="neg" />
        <Card label="Received" value={INR(kpi.received)} tone="pos" />
        <Card label="Net" value={INR(kpi.net)} tone={kpi.net < 0 ? "neg" : "pos"} />
        <Card label="Transactions" value={kpi.count.toLocaleString("en-IN")} />
      </section>

      <section className="tiles">
        <Tile label="Largest expense" value={INR(kpi.largest)} />
        <Tile label="Avg expense" value={INR(kpi.avg)} />
        <Tile label="Largest credit" value={INR(kpi.largestCr)} />
        <Tile label="Date range" value={dateRange} small />
      </section>

      {/* filters */}
      <section className="filters">
        <input className="grow" placeholder="Search merchant / description…"
          value={f.q} onChange={(e) => setFilter("q", e.target.value)} />
        <select value={f.account} onChange={(e) => setFilter("account", e.target.value)}>
          <option value="">All accounts</option>
          {accounts.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={f.type} onChange={(e) => setFilter("type", e.target.value)}>
          <option value="all">Debit + Credit</option>
          <option value="debit">Debit only</option>
          <option value="credit">Credit only</option>
        </select>
        <label className="field">From <input type="date" value={f.from} onChange={(e) => setFilter("from", e.target.value)} /></label>
        <label className="field">To <input type="date" value={f.to} onChange={(e) => setFilter("to", e.target.value)} /></label>
        <input className="num" type="number" placeholder="min ₹" value={f.min} onChange={(e) => setFilter("min", e.target.value)} />
        <input className="num" type="number" placeholder="max ₹" value={f.max} onChange={(e) => setFilter("max", e.target.value)} />
        {active && <button className="btn ghost" onClick={() => setF(EMPTY)}>Reset</button>}
      </section>

      {f.merchant && (
        <div className="chip-row">
          Filtered to merchant:
          <span className="chip">{f.merchant} <button onClick={() => setFilter("merchant", "")}>✕</button></span>
        </div>
      )}

      <div className="grid2">
        {/* by account */}
        <section className="panel">
          <h2>By account</h2>
          <table>
            <thead><tr><th>Account</th><th className="r">Debit</th><th className="r">Credit</th><th className="r">Net</th><th className="r">#</th></tr></thead>
            <tbody>
              {byAccount.map((a) => (
                <tr key={a.account}>
                  <td><span className="dot" style={{ background: acctColor(a.account) }} />{a.account}</td>
                  <td className="r num neg">{INR(a.spent)}</td>
                  <td className="r num pos">{INR(a.received)}</td>
                  <td className={`r num ${a.received - a.spent < 0 ? "neg" : "pos"}`}>{INR(a.received - a.spent)}</td>
                  <td className="r num muted">{a.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* monthly spent vs received */}
        <section className="panel">
          <div className="panel-head">
            <h2>Monthly</h2>
            <div className="legend">
              <span><i className="sw neg" /> Spent</span>
              <span><i className="sw pos" /> Received</span>
            </div>
          </div>
          <div className="bars scroll">
            {monthly.map((m) => (
              <div className="mrow" key={m.month}>
                <span className="mlabel">{m.month}</span>
                <div className="mbars">
                  <div className="track"><div className="fill neg" style={{ width: `${(m.spent / maxMonth) * 100}%` }} /></div>
                  <div className="track"><div className="fill pos" style={{ width: `${(m.received / maxMonth) * 100}%` }} /></div>
                </div>
                <span className="mval neg" title="spent">{INR(m.spent, 0)}</span>
              </div>
            ))}
            {monthly.length === 0 && <p className="muted">No dated rows.</p>}
          </div>
        </section>
      </div>

      {/* merchants — debit & credit kept separate (two-way payees), plus net */}
      <section className="panel">
        <div className="panel-head">
          <h2>Merchants <span className="muted">({merchants.length})</span></h2>
          <span className="muted">click a row to filter · click a header to sort</span>
        </div>
        <div className="tablewrap scroll">
          <table className="mtable">
            <thead>
              <tr>
                <Th label="Merchant" k="merchant" sort={mSort} setSort={setMSort} />
                <Th label="#" k="count" sort={mSort} setSort={setMSort} align="r" />
                <Th label="Debit" k="debit" sort={mSort} setSort={setMSort} align="r" />
                <Th label="Credit" k="credit" sort={mSort} setSort={setMSort} align="r" />
                <Th label="Net" k="net" sort={mSort} setSort={setMSort} align="r" />
              </tr>
            </thead>
            <tbody>
              {merchants.slice(0, 60).map((m) => (
                <tr key={m.merchant}
                  className={`clickrow ${f.merchant === m.merchant ? "on" : ""}`}
                  onClick={() => setFilter("merchant", f.merchant === m.merchant ? "" : m.merchant)}>
                  <td className="mname">{m.merchant}</td>
                  <td className="r num muted">{m.count}</td>
                  <td className="r num neg">{m.spent ? INR(m.spent) : ""}</td>
                  <td className="r num pos">{m.received ? INR(m.received) : ""}</td>
                  <td className={`r num ${m.net < 0 ? "neg" : "pos"}`}>{INR(m.net)}</td>
                </tr>
              ))}
              {merchants.length === 0 && <tr><td colSpan={5} className="muted">No merchants match.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {/* transactions */}
      <section className="panel">
        <div className="panel-head">
          <h2>Transactions</h2>
          <span className="muted">
            {sorted.length.toLocaleString("en-IN")} rows
            {sorted.length > CAP && ` (showing first ${CAP} — refine filters to narrow)`}
          </span>
        </div>
        <div className="tablewrap">
          <table className="txn">
            <thead>
              <tr>
                <Th label="Date" k="date" sort={sort} setSort={setSort} />
                <Th label="Account" k="account" sort={sort} setSort={setSort} />
                <Th label="Merchant" k="merchant" sort={sort} setSort={setSort} />
                <Th label="Description" k="description" sort={sort} setSort={setSort} />
                <Th label="Debit" k="debit" sort={sort} setSort={setSort} align="r" />
                <Th label="Credit" k="credit" sort={sort} setSort={setSort} align="r" />
                <Th label="Balance" k="balance" sort={sort} setSort={setSort} align="r" />
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, CAP).map((r, i) => (
                <tr key={i}>
                  <td className="num">{r.date}</td>
                  <td><span className="dot" style={{ background: acctColor(r.account) }} />{r.account}</td>
                  <td className="mcell" onClick={() => setFilter("merchant", r.merchant)} title="filter by this merchant">{r.merchant}</td>
                  <td className="desc" title={r.description}>{r.description}</td>
                  <td className="r num neg">{r.amount < 0 ? INR(-r.amount) : ""}</td>
                  <td className="r num pos">{r.amount > 0 ? INR(r.amount) : ""}</td>
                  <td className="r num muted">{r.balance == null ? "" : INR(r.balance)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4} className="muted">Filtered totals</td>
                <td className="r num neg">{INR(kpi.spent)}</td>
                <td className="r num pos">{INR(kpi.received)}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  );
}

function Th({ label, k, sort, setSort, align }) {
  const on = sort.key === k;
  const numeric = ["date", "debit", "credit", "balance", "net", "count"].includes(k);
  const toggle = () =>
    setSort((s) => (s.key === k ? { key: k, dir: s.dir === "asc" ? "desc" : "asc" }
                                : { key: k, dir: numeric ? "desc" : "asc" }));
  return (
    <th className={`sortable ${align || ""} ${on ? "on" : ""}`} onClick={toggle}>
      {label}<span className="arrow">{on ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}</span>
    </th>
  );
}

function Card({ label, value, tone }) {
  return (
    <div className="card">
      <div className="card-label">{label}</div>
      <div className={`card-value ${tone || ""}`}>{value}</div>
    </div>
  );
}

function Tile({ label, value, small }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className={`tile-value ${small ? "sm" : ""}`}>{value}</div>
    </div>
  );
}

function Lock() {
  return (
    <div className="lockout">
      <div className="lockout-box">
        <div className="lockout-icon">⛔</div>
        <h1>Session locked</h1>
        <p>The backend stopped responding — this happens when the offline guard detects a
          network connection and shuts everything down.</p>
        <p className="lockout-hint">Disconnect from all networks and run <code>python run.py</code> again.</p>
      </div>
    </div>
  );
}
