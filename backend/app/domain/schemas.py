import uuid
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from app.domain.enums import AnalysisStatus, SourceType


class GitImportRequest(BaseModel):
    git_url: HttpUrl
    name: str | None = Field(default=None, max_length=255)
    branch: str | None = Field(default=None, max_length=100)
    access_token: str | None = Field(
        default=None,
        description="Token opcional para clonar repositórios privados (nunca é salvo no banco)",
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
