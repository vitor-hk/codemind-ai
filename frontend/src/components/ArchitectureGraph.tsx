import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphAnalysis } from "../types/codemind";

interface ArchitectureGraphProps {
  graph: GraphAnalysis | null;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string, filePath: string) => void;
}

export function ArchitectureGraph({
  graph,
  selectedNodeId,
  onSelectNode,
}: ArchitectureGraphProps) {
  const { nodes, edges } = useMemo(() => {
    if (!graph || graph.nodes.length === 0) return { nodes: [], edges: [] };

    const sorted = [...graph.nodes].sort(
      (a, b) => a.in_degree - b.in_degree || b.out_degree - a.out_degree
    );
    const cols = Math.max(3, Math.ceil(Math.sqrt(sorted.length)));

    const flowNodes: Node[] = sorted.map((n, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const isSelected = selectedNodeId === n.id;
      const isHub = n.in_degree + n.out_degree >= 6;

      return {
        id: n.id,
        position: { x: col * 270 + (row % 2) * 50, y: row * 115 },
        data: {
          label: `${n.label}  [Ca:${n.in_degree} | Ce:${n.out_degree}]`,
          filePath: n.file_path,
        },
        style: {
          background: isSelected ? "#062e22" : "#0d1017",
          color: isSelected ? "#34d399" : "#e4e4e7",
          border: isSelected
            ? "1.5px solid #10b981"
            : isHub
            ? "1px solid #f59e0b"
            : "1px solid #222634",
          borderRadius: "4px",
          padding: "8px 10px",
          fontSize: "11px",
          fontFamily: "'JetBrains Mono', monospace",
          width: 235,
          cursor: "pointer",
          boxShadow: isSelected ? "0 0 18px rgba(16,185,129,0.2)" : "none",
        },
      };
    });

    const flowEdges: Edge[] = graph.edges.map((e, idx) => {
      const isAst = e.confidence === "HIGH_AST";
      return {
        id: `e-${idx}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label: e.relation_type,
        animated: !isAst,
        labelStyle: { fill: "#71717a", fontSize: 9, fontFamily: "JetBrains Mono" },
        labelBgStyle: { fill: "#08090c", fillOpacity: 0.9 },
        style: {
          stroke: isAst ? "#10b981" : "#f59e0b",
          strokeWidth: 1.25,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isAst ? "#10b981" : "#f59e0b",
        },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [graph, selectedNodeId]);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="h-[540px] bg-[#0b0d12] border border-[#1c1f26] flex items-center justify-center text-xs font-mono text-zinc-500">
        GRAPH_EMPTY // Sem dependências registradas para o escopo atual
      </div>
    );
  }

  return (
    <div className="relative h-[540px] w-full border border-[#1c1f26] bg-[#07080b]">
      {/* Legenda Técnica Sobreposta */}
      <div className="absolute top-3 left-3 z-10 px-3 py-1.5 bg-[#0b0d12]/90 border border-[#1c1f26] flex items-center gap-4 text-[10px] font-mono text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-0.5 bg-emerald-400 inline-block" /> AST_CONFIRMED
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-0.5 bg-amber-400 inline-block" /> SCOPED_INFERRED
        </span>
        <span>Ca: Fan-In | Ce: Fan-Out</span>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) =>
          onSelectNode(node.id, (node.data as any)?.filePath || node.id)
        }
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1c1f26" gap={24} />
        <Controls className="!bg-[#0d1017] !border-[#1c1f26] !fill-zinc-300" />
        <MiniMap
          nodeColor="#10b981"
          maskColor="rgba(8, 9, 12, 0.85)"
          className="!bg-[#0b0d12] !border-[#1c1f26]"
        />
      </ReactFlow>
    </div>
  );
}
