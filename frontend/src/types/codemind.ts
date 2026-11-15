export interface ComponentStatus {
  status: "healthy" | "degraded" | "unhealthy";
  details: Record<string, any>;
}

export interface HealthResponse {
  app_name: string;
  version: string;
  overall_status: "healthy" | "degraded" | "unhealthy";
  database: ComponentStatus;
  redis: ComponentStatus;
  ollama: ComponentStatus;
}

export interface Repository {
  id: string;
  name: string;
  description: string | null;
  source_type: string;
  source_url: string | null;
  default_branch: string;
  last_commit_hash: string | null;
  status: string;
  languages_stats: Record<string, number>;
  total_files: number;
  total_symbols: number;
  total_dependencies: number;
  total_chunks: number;
  last_analyzed_at: string | null;
  created_at: string;
}

export interface RepoFile {
  id: string;
  relative_path: string;
  language: string;
  extension: string;
  size_bytes: number;
  line_count: number;
  content_hash: string;
  is_ast_supported: boolean;
}

export interface CodeSymbol {
  id: string;
  name: string;
  qualified_name: string;
  symbol_type: string;
  language: string;
  file_path: string;
  parent_name: string | null;
  start_line: number;
  end_line: number;
  signature: string;
  documentation: string | null;
  dependencies: string[];
}

export interface SymbolRelationship {
  id: string;
  source_symbol_name: string;
  source_file_path: string;
  target_name: string;
  target_file_path: string | null;
  relation_type: string;
  confidence: string;
  line_number: number;
}

export interface GraphNodeDTO {
  id: string;
  label: string;
  node_type: string;
  file_path: string;
  in_degree: number;
  out_degree: number;
  centrality: number;
}

export interface GraphEdgeDTO {
  source: string;
  target: string;
  relation_type: string;
  confidence: string;
  weight: number;
}

export interface CoupledComponent {
  node_id: string;
  label: string;
  file_path: string;
  fan_in: number;
  fan_out: number;
  instability: number;
  centrality: number;
}

export interface GraphAnalysis {
  repository_id: string;
  scope: string;
  total_nodes: number;
  total_edges: number;
  cycles_count: number;
  circular_dependencies: string[][];
  entry_points: string[];
  top_coupled_components: CoupledComponent[];
  nodes: GraphNodeDTO[];
  edges: GraphEdgeDTO[];
}

export interface NodeNeighborhood {
  node_id: string;
  scope: string;
  direct_dependents: string[];
  transitive_dependents: string[];
  direct_dependencies: string[];
  transitive_dependencies: string[];
}

export interface SearchChunkHit {
  chunk_id: string;
  file_path: string;
  language: string;
  class_name: string | null;
  symbol_name: string;
  element_type: string;
  signature: string;
  start_line: number;
  end_line: number;
  raw_code: string;
  rrf_score: number;
  rerank_score: number;
  vector_rank: number | null;
  lexical_rank: number | null;
  match_reasons: string[];
}

export interface FileContent {
  repository_id: string;
  relative_path: string;
  language: string;
  line_count: number;
  content: string;
}

export interface CodeCitation {
  file_path: string;
  symbol_name: string;
  start_line: number;
  end_line: number;
  signature: string;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  repository_id: string;
  role: "user" | "assistant";
  intent: string | null;
  content: string;
  citations: CodeCitation[];
  execution_metrics: Record<string, any>;
  created_at: string;
}

export interface ImpactEvidenceItem {
  source_symbol: string;
  source_file_path: string;
  relation_type: string;
  confidence: string;
  line_number: number;
}

export interface ImpactAnalysis {
  repository_id: string;
  target: string;
  resolved_file_path: string;
  resolved_symbol_name: string | null;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  impact_score: number;
  confirmed_dependents: ImpactEvidenceItem[];
  inferred_dependents: ImpactEvidenceItem[];
  direct_affected_files: string[];
  transitive_affected_files: string[];
  related_test_files: string[];
  technical_justifications: string[];
}

export interface ArchitecturalSmell {
  smell_type: string;
  severity: string;
  component: string;
  description: string;
  recommendation: string;
}

export interface ArchitectureReport {
  repository_id: string;
  repository_name: string;
  overview: string;
  languages_breakdown: Record<string, number>;
  total_files: number;
  total_symbols: number;
  total_relationships: number;
  entry_points: string[];
  critical_components: CoupledComponent[];
  architectural_smells: ArchitecturalSmell[];
  improvement_suggestions: string[];
}
