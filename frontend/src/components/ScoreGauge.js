import React from "react";

export default function ScoreGauge({ score = 0 }) {
  // score between 0 and 1
  const pct = Math.max(0, Math.min(1, Number(score)));
  const width = Math.round(pct * 220);
  const label = Math.round(pct * 100);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ minWidth: 260 }}>
        <div className="gauge">
          <div className="bar" role="progressbar" aria-valuenow={label} aria-valuemin="0" aria-valuemax="100">
            <div className="fill" style={{ width: `${width}px` }} />
          </div>
          <div className="score-num">{label}% credible</div>
        </div>
      </div>
    </div>
  );
}
