import uuid
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from app.domain.enums import (
    AnalysisStatus,
    ConfidenceLevel,
    RelationType,
    SourceType,
    SymbolType,
)


class GitImportRequest(BaseModel):
    git_url: HttpUrl
    name: str | None = Field(default=None, max_length=255)
    branch: str | None = Field(default=None, max_length=100)
    access_token: str | None = Field(
        default=None,
        description="Token opcional para clonar repositórios privados",
    )


class RepositoryFileResponse(BaseModel):
    id: uuid.UUID
    relative_path: str
    language: str
    extension: str
    size_bytes: int
    line_count: int
    content_hash: str
    is_ast_supported: bool

    model_config = {"from_attributes": True}


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    source_type: SourceType
    source_url: str | None
    default_branch: str
    last_commit_hash: str | None
    status: AnalysisStatus
    error_message: str | None
    languages_stats: dict[str, int]
    total_files: int
    total_symbols: int
    total_dependencies: int
    last_analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncResultResponse(BaseModel):
    repository: RepositoryResponse
    added_files: int
    modified_files: int
    removed_files: int
    unchanged_files: int


class FileContentResponse(BaseModel):
    repository_id: uuid.UUID
    relative_path: str
    language: str
    line_count: int
    content: str


class CodeSymbolResponse(BaseModel):
    id: uuid.UUID
    name: str
    qualified_name: str
    symbol_type: SymbolType
    language: str
    file_path: str
    parent_name: str | None
    start_line: int
    end_line: int
    signature: str
    documentation: str | None
    dependencies: list[str]

    model_config = {"from_attributes": True}


class SymbolRelationshipResponse(BaseModel):
    id: uuid.UUID
    source_symbol_id: uuid.UUID | None
    source_symbol_name: str
    source_file_path: str
    target_symbol_id: uuid.UUID | None
    target_name: str
    target_file_path: str | None
    relation_type: RelationType
    confidence: ConfidenceLevel
    line_number: int

    model_config = {"from_attributes": True}


class AnalysisSummaryResponse(BaseModel):
    repository_id: uuid.UUID
    files_analyzed: int
    symbols_extracted: int
    relationships_mapped: int
    by_symbol_type: dict[str, int]
    by_confidence: dict[str, int]


class GraphNodeDTO(BaseModel):
    id: str
    label: str
    node_type: str
    file_path: str
    in_degree: int
    out_degree: int
    centrality: float


class GraphEdgeDTO(BaseModel):
    source: str
    target: str
    relation_type: str
    confidence: str
    weight: int = 1


class CoupledComponentDTO(BaseModel):
    node_id: str
    label: str
    file_path: str
    fan_in: int
    fan_out: int
    instability: float
    centrality: float


class GraphAnalysisResponse(BaseModel):
    repository_id: uuid.UUID
    scope: str
    total_nodes: int
    total_edges: int
    cycles_count: int
    circular_dependencies: list[list[str]]
    entry_points: list[str]
    top_coupled_components: list[CoupledComponentDTO]
    nodes: list[GraphNodeDTO]
    edges: list[GraphEdgeDTO]


class NodeNeighborhoodResponse(BaseModel):
    repository_id: uuid.UUID
    node_id: str
    scope: str
    direct_dependents: list[str]
    transitive_dependents: list[str]
    direct_dependencies: list[str]
    transitive_dependencies: list[str]
