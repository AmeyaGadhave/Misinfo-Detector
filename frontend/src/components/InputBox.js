import React, { useState } from "react";

export default function InputBox({ onAnalyze, loading }) {
  const [value, setValue] = useState("");

  const handleAnalyze = () => {
    if (!value) return;
    onAnalyze(value);
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <div className="input-box">
        <input
          type="text"
          placeholder="Paste article URL here (e.g. https://...)"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
        />
        <button onClick={handleAnalyze} disabled={loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>
      <div style={{ marginTop: 8, color: "#6b7280", fontSize: 13 }}>
        Example: https://www.bbc.com/news/technology-...
      </div>
    </div>
  );
}
