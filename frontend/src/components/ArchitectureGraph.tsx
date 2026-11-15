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

      return {
        id: n.id,
        position: { x: col * 260 + (row % 2) * 45, y: row * 120 },
        data: {
          label: `${n.label} (In:${n.in_degree} Out:${n.out_degree})`,
          filePath: n.file_path,
        },
        style: {
          background: isSelected ? "#1e1b4b" : "#18181b",
          color: "#f4f4f5",
          border: isSelected ? "2px solid #6366f1" : "1px solid #3f3f46",
          borderRadius: "10px",
          padding: "8px 10px",
          fontSize: "11px",
          fontFamily: "monospace",
          width: 220,
          cursor: "pointer",
        },
      };
    });

    const flowEdges: Edge[] = graph.edges.map((e, idx) => ({
      id: `e-${idx}-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      label: e.relation_type,
      animated: e.confidence !== "HIGH_AST",
      style: { stroke: e.confidence === "HIGH_AST" ? "#6366f1" : "#f59e0b" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#6366f1" },
    }));

    return { nodes: flowNodes, edges: flowEdges };
  }, [graph, selectedNodeId]);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="h-[520px] rounded-xl bg-zinc-900/60 border border-zinc-800 flex items-center justify-center text-xs text-zinc-500">
        Nenhum nó de dependência para renderizar neste repositório.
      </div>
    );
  }

  return (
    <div className="h-[520px] w-full rounded-xl overflow-hidden border border-zinc-800 bg-zinc-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) =>
          onSelectNode(node.id, (node.data as any)?.filePath || node.id)
        }
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#27272a" gap={20} />
        <Controls />
        <MiniMap nodeColor="#6366f1" maskColor="rgba(9, 9, 11, 0.75)" />
      </ReactFlow>
    </div>
  );
}
