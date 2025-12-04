// src/components/GraphView.js
import React, { useRef, useEffect } from "react";
import {ForceGraph2D} from "react-force-graph";

export default function GraphView({ graph }) {
  const fgRef = useRef();

  // Accepts graph in node-link format: { nodes: [{ id, label?, group? }], links: [{ source, target }] }
  const nodes = (graph && graph.nodes) || [];
  const links = (graph && graph.links) || [];

  // Normalize nodes: ensure each node has an id and optional group
  const normalizedNodes = nodes.map((n, idx) => {
    // nodes from networkx node_link_data may have 'id' or 'key' or 'label'
    const id = n.id ?? n.key ?? n.label ?? `node-${idx}`;
    const name = n.label ?? n.name ?? id;
    const group = n.group ?? n.type ?? null;
    return { id, name, group };
  });

  // Normalize links: ensure source/target refer to node ids
  const normalizedLinks = (links || []).map((l, idx) => {
    const source = l.source?.id ?? l.source ?? l.source_key ?? l[0] ?? null;
    const target = l.target?.id ?? l.target ?? l.target_key ?? l[1] ?? null;
    return { source, target };
  }).filter(l => l.source && l.target);

  useEffect(() => {
    if (fgRef.current) {
      // soften charge so layout is nicer
      try {
        fgRef.current.d3Force("charge").strength(-120);
      } catch (e) {
        // ignore if not available yet
      }
    }
  }, [normalizedNodes.length]);

  if (!normalizedNodes.length) {
    return <div style={{ padding: 16, color: "#6b7280" }}>No knowledge graph available.</div>;
  }

  return (
    <div style={{ height: 360 }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={{ nodes: normalizedNodes, links: normalizedLinks }}
        nodeLabel={(node) => node.name}
        nodeAutoColorBy="group"
        linkDirectionalParticles={1}
        linkDirectionalParticleSpeed={0.005}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.name;
          const fontSize = 12 / Math.log2(2 + globalScale);
          ctx.beginPath();
          ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.group ? undefined : "#888";
          ctx.fill();
          ctx.font = `${fontSize}px Sans-Serif`;
          ctx.fillStyle = "#222";
          ctx.textAlign = "center";
          ctx.fillText(label, node.x, node.y - 10);
        }}
      />
    </div>
  );
}
