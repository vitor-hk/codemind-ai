import uuid
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers.tree_sitter_engine import FileAnalysisResultDTO, TreeSitterAnalyzerEngine
from app.core.logging import get_logger
from app.domain.enums import ConfidenceLevel, RelationType, SymbolType
from app.domain.schemas import AnalysisSummaryResponse
from app.infrastructure.database.models import (
    CodeSymbolModel,
    RepositoryFileModel,
    RepositoryModel,
    SymbolRelationshipModel,
)

logger = get_logger(__name__)
analyzer_engine = TreeSitterAnalyzerEngine()


class CodeAnalysisService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analyze_repository(self, repo_id: uuid.UUID) -> AnalysisSummaryResponse:
        repo_stmt = select(RepositoryModel).where(RepositoryModel.id == repo_id)
        repo_res = await self.db.execute(repo_stmt)
        repo = repo_res.scalar_one_or_none()
        if not repo:
            raise ValueError("Repositório não encontrado para análise.")

        await self.db.execute(
            delete(SymbolRelationshipModel).where(SymbolRelationshipModel.repository_id == repo_id)
        )
        await self.db.execute(
            delete(CodeSymbolModel).where(CodeSymbolModel.repository_id == repo_id)
        )
        await self.db.flush()

        files_stmt = select(RepositoryFileModel).where(
            RepositoryFileModel.repository_id == repo_id,
            RepositoryFileModel.is_ast_supported.is_(True),
        )
        files_res = await self.db.execute(files_stmt)
        ast_files = list(files_res.scalars().all())

        root_path = Path(repo.local_path).resolve()
        file_results: list[tuple[RepositoryFileModel, FileAnalysisResultDTO]] = []

        for file_model in ast_files:
            abs_path = (root_path / file_model.relative_path).resolve()
            if not abs_path.is_file():
                continue
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            parsed = analyzer_engine.analyze_file(
                file_path=file_model.relative_path,
                language=file_model.language,
                content=content,
            )
            file_results.append((file_model, parsed))

        symbol_models: list[CodeSymbolModel] = []
        symbols_by_name: dict[str, list[CodeSymbolModel]] = {}
        raw_symbols_pairs = []

        for file_model, parsed in file_results:
            for sym_dto in parsed.symbols:
                deps = sorted({c[0] for c in sym_dto.calls} | set(sym_dto.bases))
                sym_model = CodeSymbolModel(
                    id=uuid.uuid4(),
                    repository_id=repo.id,
                    file_id=file_model.id,
                    name=sym_dto.name,
                    qualified_name=sym_dto.qualified_name,
                    symbol_type=sym_dto.symbol_type,
                    language=sym_dto.language,
                    file_path=sym_dto.file_path,
                    parent_name=sym_dto.parent_name,
                    start_line=sym_dto.start_line,
                    end_line=sym_dto.end_line,
                    signature=sym_dto.signature,
                    documentation=sym_dto.documentation,
                    dependencies=deps,
                )
                self.db.add(sym_model)
                symbol_models.append(sym_model)
                symbols_by_name.setdefault(sym_dto.name, []).append(sym_model)
                raw_symbols_pairs.append((sym_model, sym_dto, parsed.imports))

        await self.db.flush()

        relationship_models: list[SymbolRelationshipModel] = []

        for file_model, parsed in file_results:
            for imp_name, line_no in parsed.imports:
                short_target = imp_name.split(".")[-1].split("/")[-1]
                matched_targets = symbols_by_name.get(short_target, [])
                target_sym = matched_targets[0] if matched_targets else None

                rel = SymbolRelationshipModel(
                    repository_id=repo.id,
                    source_symbol_id=None,
                    source_symbol_name=Path(file_model.relative_path).stem,
                    source_file_path=file_model.relative_path,
                    target_symbol_id=target_sym.id if target_sym else None,
                    target_name=imp_name,
                    target_file_path=target_sym.file_path if target_sym else None,
                    relation_type=RelationType.IMPORTS,
                    confidence=ConfidenceLevel.HIGH_AST,
                    line_number=line_no,
                )
                self.db.add(rel)
                relationship_models.append(rel)

        for sym_model, sym_dto, file_imports in raw_symbols_pairs:
            imported_short_names = {
                imp[0].split(".")[-1].split("/")[-1] for imp in file_imports
            }

            for base_name in sym_dto.bases:
                candidates = symbols_by_name.get(base_name, [])
                target_sym = candidates[0] if candidates else None
                rel = SymbolRelationshipModel(
                    repository_id=repo.id,
                    source_symbol_id=sym_model.id,
                    source_symbol_name=sym_model.qualified_name,
                    source_file_path=sym_model.file_path,
                    target_symbol_id=target_sym.id if target_sym else None,
                    target_name=base_name,
                    target_file_path=target_sym.file_path if target_sym else None,
                    relation_type=RelationType.INHERITS,
                    confidence=ConfidenceLevel.HIGH_AST,
                    line_number=sym_model.start_line,
                )
                self.db.add(rel)
                relationship_models.append(rel)

            for called_name, call_line in sym_dto.calls:
                candidates = symbols_by_name.get(called_name, [])
                target_sym: CodeSymbolModel | None = None
                confidence = ConfidenceLevel.LOW_HEURISTIC

                same_file = [c for c in candidates if c.file_path == sym_model.file_path]
                if same_file:
                    target_sym = same_file[0]
                    confidence = ConfidenceLevel.HIGH_AST
                elif called_name in imported_short_names and candidates:
                    target_sym = candidates[0]
                    confidence = ConfidenceLevel.MEDIUM_SCOPED
                elif len(candidates) == 1:
                    target_sym = candidates[0]
                    confidence = ConfidenceLevel.LOW_HEURISTIC

                if target_sym or called_name in imported_short_names:
                    rel = SymbolRelationshipModel(
                        repository_id=repo.id,
                        source_symbol_id=sym_model.id,
                        source_symbol_name=sym_model.qualified_name,
                        source_file_path=sym_model.file_path,
                        target_symbol_id=target_sym.id if target_sym else None,
                        target_name=target_sym.qualified_name if target_sym else called_name,
                        target_file_path=target_sym.file_path if target_sym else None,
                        relation_type=RelationType.CALLS,
                        confidence=confidence,
                        line_number=call_line,
                    )
                    self.db.add(rel)
                    relationship_models.append(rel)

        repo.total_symbols = len(symbol_models)
        repo.total_dependencies = len(relationship_models)
        await self.db.commit()

        by_type: dict[str, int] = {}
        for s in symbol_models:
            by_type[s.symbol_type.value] = by_type.get(s.symbol_type.value, 0) + 1

        by_conf: dict[str, int] = {}
        for r in relationship_models:
            by_conf[r.confidence.value] = by_conf.get(r.confidence.value, 0) + 1

        logger.info(
            "repository_ast_analyzed",
            repo_id=str(repo.id),
            symbols=len(symbol_models),
            relationships=len(relationship_models),
        )

        return AnalysisSummaryResponse(
            repository_id=repo.id,
            files_analyzed=len(file_results),
            symbols_extracted=len(symbol_models),
            relationships_mapped=len(relationship_models),
            by_symbol_type=by_type,
            by_confidence=by_conf,
        )

    async def list_symbols(
        self,
        repo_id: uuid.UUID,
        symbol_type: SymbolType | None = None,
        file_path: str | None = None,
        search: str | None = None,
    ) -> list[CodeSymbolModel]:
        stmt = select(CodeSymbolModel).where(CodeSymbolModel.repository_id == repo_id)
        if symbol_type:
            stmt = stmt.where(CodeSymbolModel.symbol_type == symbol_type)
        if file_path:
            stmt = stmt.where(CodeSymbolModel.file_path == file_path)
        if search:
            stmt = stmt.where(CodeSymbolModel.qualified_name.ilike(f"%{search}%"))
        stmt = stmt.order_by(CodeSymbolModel.file_path.asc(), CodeSymbolModel.start_line.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_relationships(
        self,
        repo_id: uuid.UUID,
        relation_type: RelationType | None = None,
        confidence: ConfidenceLevel | None = None,
    ) -> list[SymbolRelationshipModel]:
        stmt = select(SymbolRelationshipModel).where(
            SymbolRelationshipModel.repository_id == repo_id
        )
        if relation_type:
            stmt = stmt.where(SymbolRelationshipModel.relation_type == relation_type)
        if confidence:
            stmt = stmt.where(SymbolRelationshipModel.confidence == confidence)
        stmt = stmt.order_by(
            SymbolRelationshipModel.source_file_path.asc(),
            SymbolRelationshipModel.line_number.asc(),
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
