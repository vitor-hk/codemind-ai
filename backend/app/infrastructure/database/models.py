import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.domain.enums import AnalysisStatus, ConfidenceLevel, RelationType, SourceType, SymbolType
from app.infrastructure.database.base import Base, TimestampMixin


class RepositoryModel(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type_enum"), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    local_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    last_commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status_enum"), default=AnalysisStatus.PENDING, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages_stats: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_symbols: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_dependencies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    files: Mapped[list["RepositoryFileModel"]] = relationship("RepositoryFileModel", back_populates="repository", cascade="all, delete-orphan")
    symbols: Mapped[list["CodeSymbolModel"]] = relationship("CodeSymbolModel", back_populates="repository", cascade="all, delete-orphan")
    relationships: Mapped[list["SymbolRelationshipModel"]] = relationship("SymbolRelationshipModel", back_populates="repository", cascade="all, delete-orphan")
    chunks: Mapped[list["CodeChunkModel"]] = relationship("CodeChunkModel", back_populates="repository", cascade="all, delete-orphan")


class RepositoryFileModel(Base, TimestampMixin):
    __tablename__ = "repository_files"
    __table_args__ = (UniqueConstraint("repository_id", "relative_path", name="uq_repo_relative_path"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_ast_supported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="files")
    symbols: Mapped[list["CodeSymbolModel"]] = relationship("CodeSymbolModel", back_populates="file", cascade="all, delete-orphan")


class CodeSymbolModel(Base, TimestampMixin):
    __tablename__ = "code_symbols"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    qualified_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    symbol_type: Mapped[SymbolType] = mapped_column(Enum(SymbolType, name="symbol_type_enum"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    parent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    documentation: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="symbols")
    file: Mapped["RepositoryFileModel"] = relationship("RepositoryFileModel", back_populates="symbols")


class SymbolRelationshipModel(Base, TimestampMixin):
    __tablename__ = "symbol_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    source_symbol_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("code_symbols.id", ondelete="CASCADE"), nullable=True, index=True)
    source_symbol_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_symbol_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    target_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    relation_type: Mapped[RelationType] = mapped_column(Enum(RelationType, name="relation_type_enum"), nullable=False, index=True)
    confidence: Mapped[ConfidenceLevel] = mapped_column(Enum(ConfidenceLevel, name="confidence_level_enum"), default=ConfidenceLevel.HIGH_AST, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="relationships")


class CodeChunkModel(Base, TimestampMixin):
    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    symbol_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    element_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contextual_content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_code: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)

    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="chunks")
