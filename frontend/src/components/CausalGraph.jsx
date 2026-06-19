import React, { useEffect, useRef, useState } from "react";

const NODE_TYPE_COLOR = {
  action:    "#6b0f0f",
  state:     "#122640",
  milestone: "#2a1040",
  outcome:   "#3a2e00",
};

const STATE_OPACITY = {
  determined:   1.0,
  undetermined: 0.35,
};

function buildElements(worldState, beliefs, dagNodes, dagEdges) {
  const nodes = dagNodes.map((n) => {
    const state = worldState[n.id];
    const belief = beliefs?.find((b) => b.node_id === n.id);
    const isDetermined = state && state !== "unknown";
    return {
      data: {
        id: n.id,
        label: n.id.replace(/_/g, "\n"),
        nodeType: n.type,
        state: state || "?",
        confidence: belief ? Math.max(...Object.values(belief.states)) : null,
        isDetermined,
      },
    };
  });

  const edges = dagEdges.map((e, i) => ({
    data: { id: `e${i}`, source: e.source, target: e.target, weight: e.weight },
  }));

  return [...nodes, ...edges];
}

function FallbackGraph({ worldState, beliefs }) {
  return (
    <div className="p-4 space-y-1 overflow-y-auto h-full" style={{ fontSize: "0.7rem" }}>
      <div className="uppercase tracking-widest mb-2"
        style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}>
        World Nodes
      </div>
      {Object.entries(worldState || {}).map(([node, state]) => {
        const belief = beliefs?.find((b) => b.node_id === node);
        const conf = belief ? Math.max(...Object.values(belief.states)) : null;
        return (
          <div key={node}
            className="flex justify-between py-1 capitalize"
            style={{ borderBottom: "1px solid var(--border-dim)", color: "var(--parchment-dim)" }}
          >
            <span>{node.replace(/_/g, " ")}</span>
            <span style={{ color: "var(--gold-text)" }}>
              {state}
              {conf !== null && (
                <span style={{ color: "var(--mist)", marginLeft: 4 }}>
                  {(conf * 100).toFixed(0)}%
                </span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function CausalGraph({ worldState, beliefs, dagMeta }) {
  const containerRef = useRef(null);
  const cyRef        = useRef(null);
  // cytoscape is lazy-loaded once on mount; null = not yet loaded, false = unavailable
  const [cytoscape, setCytoscape] = useState(null);

  // ── Lazy-load cytoscape on first mount ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    import("cytoscape")
      .then((mod) => { if (!cancelled) setCytoscape(() => mod.default); })
      .catch(() => { if (!cancelled) setCytoscape(false); });
    return () => { cancelled = true; };
  }, []);

  // ── Build / rebuild the graph whenever data or cytoscape changes ─────────────
  useEffect(() => {
    if (!cytoscape || !containerRef.current || !dagMeta) return;

    const elements = buildElements(
      worldState || {},
      beliefs    || [],
      dagMeta.nodes,
      dagMeta.edges,
    );

    cyRef.current?.destroy();

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "7px",
            "font-family": "Georgia, serif",
            color: "#d8ccb0",
            "text-wrap": "wrap",
            "background-color": (ele) => NODE_TYPE_COLOR[ele.data("nodeType")] || "#333",
            opacity: (ele) => ele.data("isDetermined") ? STATE_OPACITY.determined : STATE_OPACITY.undetermined,
            width: 58,
            height: 38,
            shape: (ele) =>
              ele.data("nodeType") === "outcome"   ? "diamond"
              : ele.data("nodeType") === "milestone" ? "hexagon"
              : "roundrectangle",
          },
        },
        {
          selector: "edge",
          style: {
            width: (ele) => Math.max(1, (ele.data("weight") || 1) * 1.5),
            "line-color": "#1a1a2a",
            "target-arrow-color": "#2a1a1a",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.7,
          },
        },
      ],
      layout: {
        name: "breadthfirst",
        directed: true,
        spacingFactor: 1.4,
        padding: 20,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
    });

    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [cytoscape, worldState, beliefs, dagMeta]);

  // cytoscape === null  → still loading
  // cytoscape === false → load failed, use fallback
  if (cytoscape === false || !dagMeta) {
    return <FallbackGraph worldState={worldState} beliefs={beliefs} />;
  }

  return (
    <div className="relative w-full h-full">
      {cytoscape === null && (
        <div className="absolute inset-0 flex items-center justify-center"
          style={{ color: "var(--mist)", fontFamily: "Cinzel, serif", fontSize: "0.6rem" }}>
          Loading graph…
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
