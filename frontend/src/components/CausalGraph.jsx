import React, { useEffect, useRef } from "react";

// Attempt to use Cytoscape; graceful fallback if not installed.
let cytoscape;
try {
  cytoscape = (await import("cytoscape")).default;
} catch {
  cytoscape = null;
}

const NODE_TYPE_COLOR = {
  action:    "#6b0f0f",
  state:     "#122640",
  milestone: "#2a1040",
  outcome:   "#3a2e00",
};

const STATE_OPACITY = {
  // Nodes with a determined state are bright; undetermined are dim
  determined: 1.0,
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
    data: {
      id: `e${i}`,
      source: e.source,
      target: e.target,
      weight: e.weight,
    },
  }));

  return [...nodes, ...edges];
}

function FallbackGraph({ worldState, beliefs }) {
  return (
    <div className="p-4 space-y-1 overflow-y-auto h-full">
      <div className="text-xs text-mist mb-2 uppercase tracking-wider">World State</div>
      {Object.entries(worldState || {}).map(([node, state]) => {
        const belief = beliefs?.find((b) => b.node_id === node);
        const conf = belief ? Math.max(...Object.values(belief.states)) : null;
        return (
          <div key={node} className="flex justify-between text-xs border-b border-[#2a2a4c] py-1">
            <span className="text-parchment capitalize">{node.replace(/_/g, " ")}</span>
            <span className="text-gold">
              {state}
              {conf !== null && (
                <span className="text-mist ml-1">({(conf * 100).toFixed(0)}%)</span>
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
  const cyRef = useRef(null);

  useEffect(() => {
    if (!cytoscape || !containerRef.current || !dagMeta) return;

    const elements = buildElements(
      worldState || {},
      beliefs || [],
      dagMeta.nodes,
      dagMeta.edges
    );

    if (cyRef.current) {
      cyRef.current.destroy();
    }

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
            "font-size": "8px",
            "font-family": "Georgia, serif",
            color: "#f5f0e8",
            "text-wrap": "wrap",
            "background-color": (ele) =>
              NODE_TYPE_COLOR[ele.data("nodeType")] || "#555",
            opacity: (ele) =>
              ele.data("isDetermined")
                ? STATE_OPACITY.determined
                : STATE_OPACITY.undetermined,
            width: 60,
            height: 40,
            shape: (ele) =>
              ele.data("nodeType") === "outcome"
                ? "diamond"
                : ele.data("nodeType") === "milestone"
                ? "hexagon"
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
      autolock: false,
    });

    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [worldState, beliefs, dagMeta]);

  if (!cytoscape || !dagMeta) {
    return <FallbackGraph worldState={worldState} beliefs={beliefs} />;
  }

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      <div className="absolute bottom-2 left-2 flex gap-2 flex-wrap">
        {Object.entries(NODE_TYPE_COLOR).map(([type, color]) => (
          <span key={type} className="text-xs flex items-center gap-1">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ backgroundColor: color }}
            />
            <span className="text-mist capitalize">{type}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
