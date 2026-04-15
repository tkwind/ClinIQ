import { useState } from "react";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [query, setQuery] = useState("lung cancer");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Request failed");
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: "1rem", fontFamily: "sans-serif" }}>
      <h1>AI Medical Research Assistant (Phase 1)</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter disease query"
          style={{ width: "300px", marginRight: "0.5rem" }}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search PubMed"}
        </button>
      </form>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <ul>
        {results.map((item, idx) => (
          <li key={`${item.title}-${idx}`}>
            <strong>{item.title}</strong>
            <div>Publication Date: {item.pub_date || "N/A"}</div>
            <div>Source: {item.source}</div>
          </li>
        ))}
      </ul>
    </main>
  );
}
