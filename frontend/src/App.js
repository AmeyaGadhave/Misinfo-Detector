// src/App.js
import React, { useState } from "react";
import api from "./api"; // axios instance (baseURL -> http://127.0.0.1:8000/api)
import GraphView from "./components/GraphView";
import ScoreGauge from "./components/ScoreGauge"; // if you have it; else use simple bar
import "./App.css";

// small frontend marker as requested
// __define-ocg__
const varOcg = { frontendMode: "dashboard-llm-kg" };
const varFiltersCg = { domains: [], min_reliability: 0.0 };

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const analyze = async () => {
    if (!url.trim()) {
      setError("Please paste a valid article URL.");
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await api.post("/detect", { url: url.trim() });
      setResult(res.data);
    } catch (e) {
      console.error(e);
      setError(e?.response?.data || e.message || "Network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">AI-Powered Misinformation Detector</div>
        <div className="subtitle">Evidence-based article analysis • LLM summaries • Knowledge graph</div>
      </header>

      <main className="main">
        <section className="panel input-panel">
          <input
            className="url-input"
            placeholder="Paste article URL here (e.g. https://www.bbc.com/news/...)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button className="btn primary" onClick={analyze} disabled={loading}>
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </section>

        {error && <div className="panel error">{String(error)}</div>}

        {result && (
          <>
            <section className="panel summary-panel">
              <div className="summary-left">
                <h2 className="title">{result.title}</h2>
                <div className="meta">
                  <div className="cred-block">
                    <div className="cred-label">Credibility</div>
                    <div className="cred-value">{Math.round((result.credibility_score || 0) * 100)}%</div>
                  </div>
                  <div className="stance-block">
                    <div className={`badge stance ${result.stance?.stance || "mixed"}`}>
                      {result.stance?.stance || "mixed"}
                    </div>
                    <div className="bias">{result.bias_note || "Bias check not available"}</div>
                  </div>
                </div>
                <p className="summary-text">{result.summary}</p>
              </div>

              <div className="summary-right">
                {/* If you have a ScoreGauge component, show it; else show a styled bar */}
                <div style={{ marginBottom: 16 }}>
                  <ScoreGauge score={(result.credibility_score || 0) * 100} />
                </div>
                <div className="actions">
                  <button
                    className="btn"
                    onClick={() => {
                      const b = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
                      const u = URL.createObjectURL(b);
                      const a = document.createElement("a");
                      a.href = u; a.download = "analysis.json"; a.click();
                      URL.revokeObjectURL(u);
                    }}
                  >
                    Download JSON
                  </button>
                </div>
              </div>
            </section>

            <section className="panel evidence-panel">
              <h3>Top Evidence</h3>
              <div className="evidence-grid">
                {(result.evidence || []).map((ev, i) => (
                  <div className="evidence-card" key={i}>
                    <div className="evidence-title">Evidence #{i + 1}</div>
                    <div className="evidence-text">{ev}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel kg-panel">
              <h3>Knowledge Graph</h3>
              {result.knowledge_graph && result.knowledge_graph.nodes?.length > 0 ? (
                <GraphView graph={result.knowledge_graph} />
              ) : (
                <div className="empty">No knowledge graph available.</div>
              )}
            </section>
          </>
        )}

        {!result && !error && (
          <div className="panel hint">
            Tip: Use news articles (BBC/CNN/Reuters) for full LLM-powered summaries. Some paywalled sites block scraping.
          </div>
        )}
      </main>

      <footer className="footer">
        Prototype — for research only. Not a final arbiter of truth.
      </footer>
    </div>
  );
}
