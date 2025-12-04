import React from "react";

export default function EvidenceCard({ text, index }) {
  return (
    <div className="ev-card">
      <h4>Evidence #{index}</h4>
      <p>{text}</p>
    </div>
  );
}
