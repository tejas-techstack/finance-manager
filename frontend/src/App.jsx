import { useEffect, useState } from "react";
import axios from "axios";

function App() {
  const [stats, setStats] = useState([]);
  const [transactions, setTransactions] = useState([]);

  const upload = async (e) => {
    const file = e.target.files[0];

    const form = new FormData();

    form.append("file", file);

    await axios.post(
      "http://127.0.0.1:8000/upload",
      form
    );

    load();
  };

  const load = async () => {
    const s = await axios.get(
      "http://127.0.0.1:8000/stats"
    );

    const t = await axios.get(
      "http://127.0.0.1:8000/transactions"
    );

    setStats(s.data);
    setTransactions(t.data);
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>Semantic Expense Manager</h1>

      <input
        type="file"
        onChange={upload}
      />

      <h2>Merchant Totals</h2>

      {stats.map((s, i) => (
        <div key={i}>
          {s.merchant} — ₹{s.total}
        </div>
      ))}

      <h2>Transactions</h2>

      {transactions.map((t, i) => (
        <div
          key={i}
          style={{
            border: "1px solid #ccc",
            padding: 10,
            marginBottom: 10
          }}
        >
          <div>{t.merchant}</div>
          <div>₹{t.amount}</div>
          <div>{t.description}</div>
        </div>
      ))}
    </div>
  );
}

export default App;
