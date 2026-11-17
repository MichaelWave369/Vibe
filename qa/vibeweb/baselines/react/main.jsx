import React, { useState } from "react";
import { createRoot } from "react-dom/client";

function CounterCard({ label, total, incrementTotal }) {
  const [count, setCount] = useState(0);
  return <section aria-label={label}>
    <h2>{label}</h2>
    <p>{label}: {count} clicks. Shared total: {total}</p>
    <button type="button" onClick={() => setCount(n => Math.min(9, n + 1))}>Increment local</button>
    <button type="button" onClick={incrementTotal}>Increment total</button>
  </section>;
}

function App() {
  const [total, setTotal] = useState(0);
  const incrementTotal = () => setTotal(n => Math.min(369, n + 1));
  return <main>
    <h1>Two counters. One language.</h1>
    <p data-bench-shared>Shared total across cards: {total}</p>
    <button type="button" onClick={() => setTotal(0)}>Reset shared total</button>
    <CounterCard label="Alpha" total={total} incrementTotal={incrementTotal} />
    <CounterCard label="Beta" total={total} incrementTotal={incrementTotal} />
  </main>;
}
createRoot(document.getElementById("root")).render(<App />);
