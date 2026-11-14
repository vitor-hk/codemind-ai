from itertools import islice
import networkx as nx

from app.domain.schemas import (
    CoupledComponentDTO,
    GraphAnalysisResponse,
    GraphEdgeDTO,
    GraphNodeDTO,
    NodeNeighborhoodResponse,
)
from app.infrastructure.database.models import (
    CodeSymbolModel,
    RepositoryFileModel,
    SymbolRelationshipModel,
)


class DependencyGraphEngine:
    """Motor de grafos direcionados com NetworkX para análise de arquitetura e dependências."""

    @staticmethod
    def build_file_graph(
        files: list[RepositoryFileModel],
        relationships: list[SymbolRelationshipModel],
    ) -> nx.DiGraph:
        graph = nx.DiGraph()
        for f in files:
            graph.add_node(
                f.relative_path,
                label=f.relative_path.split("/")[-1],
                node_type="file",
                file_path=f.relative_path,
                language=f.language,
            )

        for rel in relationships:
            src = rel.source_file_path
            dst = rel.target_file_path
            if not src or not dst or src == dst:
                continue
            if not graph.has_node(src):
                graph.add_node(
                    src, label=src.split("/")[-1], node_type="file", file_path=src
                )
            if not graph.has_node(dst):
                graph.add_node(
                    dst, label=dst.split("/")[-1], node_type="file", file_path=dst
                )

            if graph.has_edge(src, dst):
                graph[src][dst]["weight"] += 1
            else:
                graph.add_edge(
                    src,
                    dst,
                    relation_type=rel.relation_type.value,
                    confidence=rel.confidence.value,
                    weight=1,
                )
        return graph

    @staticmethod
    def build_symbol_graph(
        symbols: list[CodeSymbolModel],
        relationships: list[SymbolRelationshipModel],
    ) -> nx.DiGraph:
        graph = nx.DiGraph()
        sym_by_id = {s.id: s for s in symbols}

        for s in symbols:
            node_key = f"{s.file_path}::{s.qualified_name}"
            graph.add_node(
                node_key,
                label=s.qualified_name,
                node_type=s.symbol_type.value,
                file_path=s.file_path,
            )

        for rel in relationships:
            if not rel.source_symbol_id or not rel.target_symbol_id:
                continue
            src_sym = sym_by_id.get(rel.source_symbol_id)
            dst_sym = sym_by_id.get(rel.target_symbol_id)
            if not src_sym or not dst_sym:
                continue

            src_key = f"{src_sym.file_path}::{src_sym.qualified_name}"
            dst_key = f"{dst_sym.file_path}::{dst_sym.qualified_name}"
            if src_key == dst_key:
                continue

            if graph.has_edge(src_key, dst_key):
                graph[src_key][dst_key]["weight"] += 1
            else:
                graph.add_edge(
                    src_key,
                    dst_key,
                    relation_type=rel.relation_type.value,
                    confidence=rel.confidence.value,
                    weight=1,
                )
        return graph

    def analyze_graph(
        self,
        repo_id,
        graph: nx.DiGraph,
        scope: str = "file",
        max_nodes: int = 80,
    ) -> GraphAnalysisResponse:
        total_nodes = graph.number_of_nodes()
        total_edges = graph.number_of_edges()

        if total_nodes > 0:
            centrality_map = nx.degree_centrality(graph)
        else:
            centrality_map = {}

        cycles: list[list[str]] = []
        if total_edges > 0:
            try:
                raw_cycles = islice(nx.simple_cycles(graph), 20)
                cycles = [list(c) for c in raw_cycles]
            except Exception:
                cycles = []

        entry_points: list[str] = []
        coupled_list: list[CoupledComponentDTO] = []

        for node_id, data in graph.nodes(data=True):
            fan_in = graph.in_degree(node_id)
            fan_out = graph.out_degree(node_id)
            total_deg = fan_in + fan_out
            instability = round(fan_out / total_deg, 3) if total_deg > 0 else 0.0
            cent = round(centrality_map.get(node_id, 0.0), 4)

            if fan_in == 0 and fan_out > 0:
                entry_points.append(node_id)

            if total_deg > 0:
                coupled_list.append(
                    CoupledComponentDTO(
                        node_id=node_id,
                        label=data.get("label", node_id),
                        file_path=data.get("file_path", node_id),
                        fan_in=fan_in,
                        fan_out=fan_out,
                        instability=instability,
                        centrality=cent,
                    )
                )

        coupled_list.sort(key=lambda x: (x.fan_in + x.fan_out, x.centrality), reverse=True)
        top_coupled = coupled_list[:15]

        ranked_node_ids = [
            n
            for n, _ in sorted(
                graph.nodes(data=True),
                key=lambda item: graph.degree(item[0]),
                reverse=True,
            )[:max_nodes]
        ]
        subgraph = graph.subgraph(ranked_node_ids)

        nodes_dto = [
            GraphNodeDTO(
                id=n,
                label=data.get("label", n),
                node_type=data.get("node_type", scope),
                file_path=data.get("file_path", n),
                in_degree=graph.in_degree(n),
                out_degree=graph.out_degree(n),
                centrality=round(centrality_map.get(n, 0.0), 4),
            )
            for n, data in subgraph.nodes(data=True)
        ]

        edges_dto = [
            GraphEdgeDTO(
                source=u,
                target=v,
                relation_type=edata.get("relation_type", "DEPENDS_ON"),
                confidence=edata.get("confidence", "HIGH_AST"),
                weight=edata.get("weight", 1),
            )
            for u, v, edata in subgraph.edges(data=True)
        ]

        return GraphAnalysisResponse(
            repository_id=repo_id,
            scope=scope,
            total_nodes=total_nodes,
            total_edges=total_edges,
            cycles_count=len(cycles),
            circular_dependencies=cycles,
            entry_points=sorted(entry_points)[:25],
            top_coupled_components=top_coupled,
            nodes=nodes_dto,
            edges=edges_dto,
        )

    @staticmethod
    def get_node_neighborhood(
        repo_id,
        graph: nx.DiGraph,
        node_id: str,
        scope: str,
    ) -> NodeNeighborhoodResponse:
        if not graph.has_node(node_id):
            matches = [n for n in graph.nodes if node_id in n]
            if matches:
                node_id = matches[0]
            else:
                return NodeNeighborhoodResponse(
                    repository_id=repo_id,
                    node_id=node_id,
                    scope=scope,
                    direct_dependents=[],
                    transitive_dependents=[],
                    direct_dependencies=[],
                    transitive_dependencies=[],
                )

        direct_dependents = sorted(list(graph.predecessors(node_id)))
        direct_dependencies = sorted(list(graph.successors(node_id)))

        all_ancestors = nx.ancestors(graph, node_id)
        transitive_dependents = sorted(list(all_ancestors - set(direct_dependents)))

        all_descendants = nx.descendants(graph, node_id)
        transitive_dependencies = sorted(list(all_descendants - set(direct_dependencies)))

        return NodeNeighborhoodResponse(
            repository_id=repo_id,
            node_id=node_id,
            scope=scope,
            direct_dependents=direct_dependents,
            transitive_dependents=transitive_dependents,
            direct_dependencies=direct_dependencies,
            transitive_dependencies=transitive_dependencies,
        )
