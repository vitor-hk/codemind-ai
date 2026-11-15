import uuid
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ConfidenceLevel
from app.domain.schemas import (
    ArchitecturalSmellDTO,
    ImpactAnalysisResponse,
    ImpactEvidenceItemDTO,
    RepositoryArchitectureReportResponse,
)
from app.infrastructure.database.models import (
    CodeSymbolModel,
    RepositoryFileModel,
    SymbolRelationshipModel,
)
from app.services.graph_service import GraphService
from app.services.repository_service import RepositoryService


class ImpactAnalysisService:
    """Motor de análise de impacto de modificações e diagnóstico arquitetural."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analyze_change_impact(
        self, repo_id: uuid.UUID, target: str
    ) -> ImpactAnalysisResponse:
        clean_target = target.strip()
        await RepositoryService(self.db).get_repository(repo_id)

        sym_stmt = select(CodeSymbolModel).where(
            CodeSymbolModel.repository_id == repo_id,
            or_(
                CodeSymbolModel.qualified_name == clean_target,
                CodeSymbolModel.name == clean_target,
                CodeSymbolModel.file_path == clean_target,
                CodeSymbolModel.qualified_name.ilike(f"%{clean_target}%"),
            ),
        )
        sym_res = await self.db.execute(sym_stmt)
        matched_symbols = list(sym_res.scalars().all())

        resolved_file = clean_target
        resolved_sym_name: str | None = None
        target_names: set[str] = {clean_target.split("/")[-1].replace(".py", "")}

        if matched_symbols:
            primary = matched_symbols[0]
            resolved_file = primary.file_path
            resolved_sym_name = primary.qualified_name
            for s in matched_symbols[:5]:
                target_names.add(s.name)
                target_names.add(s.qualified_name)

        rel_stmt = select(SymbolRelationshipModel).where(
            SymbolRelationshipModel.repository_id == repo_id,
            or_(
                SymbolRelationshipModel.target_file_path == resolved_file,
                SymbolRelationshipModel.target_name.in_(list(target_names)),
            ),
        )
        rel_res = await self.db.execute(rel_stmt)
        incoming_rels = list(rel_res.scalars().all())

        confirmed_deps: list[ImpactEvidenceItemDTO] = []
        inferred_deps: list[ImpactEvidenceItemDTO] = []

        for rel in incoming_rels:
            item = ImpactEvidenceItemDTO(
                source_symbol=rel.source_symbol_name,
                source_file_path=rel.source_file_path,
                relation_type=rel.relation_type.value,
                confidence=rel.confidence.value,
                line_number=rel.line_number,
            )
            if rel.confidence == ConfidenceLevel.HIGH_AST:
                confirmed_deps.append(item)
            else:
                inferred_deps.append(item)

        graph_service = GraphService(self.db)
        neighborhood = await graph_service.get_node_neighborhood(
            repo_id=repo_id, node_id=resolved_file, scope="file"
        )

        direct_files = sorted(
            set(neighborhood.direct_dependents)
            | {r.source_file_path for r in incoming_rels if r.source_file_path != resolved_file}
        )
        transitive_files = sorted(
            set(neighborhood.transitive_dependents) - set(direct_files) - {resolved_file}
        )

        files_res = await self.db.execute(
            select(RepositoryFileModel).where(RepositoryFileModel.repository_id == repo_id)
        )
        all_files = [f.relative_path for f in files_res.scalars().all()]

        stem = resolved_file.split("/")[-1].split(".")[0].lower()
        related_tests: list[str] = []
        for fpath in all_files:
            lower_p = fpath.lower()
            is_test = "test" in lower_p or "spec" in lower_p
            if is_test and (
                fpath in direct_files
                or fpath in transitive_files
                or stem in lower_p
            ):
                related_tests.append(fpath)

        impact_score = (
            len(confirmed_deps) * 12
            + len(inferred_deps) * 6
            + len(direct_files) * 15
            + len(transitive_files) * 8
        )

        if impact_score >= 70 or len(direct_files) >= 5:
            risk_level = "CRITICAL"
        elif impact_score >= 35 or len(direct_files) >= 2:
            risk_level = "HIGH"
        elif impact_score >= 12 or len(confirmed_deps) >= 1 or len(inferred_deps) >= 1:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        justifications = [
            f"Alvo analisado: `{resolved_sym_name or resolved_file}` localizado em `{resolved_file}`.",
            f"Foram encontradas {len(confirmed_deps)} dependências estáticas confirmadas via AST (HIGH_AST) e {len(inferred_deps)} relações inferidas/escopadas.",
            f"A alteração afeta diretamente {len(direct_files)} arquivo(s) e propaga impacto transitivo para outros {len(transitive_files)} módulo(s) no grafo.",
        ]
        if related_tests:
            justifications.append(
                f"Foram identificados {len(related_tests)} arquivo(s) de teste automatizado cobrindo direta ou indiretamente este componente."
            )
        else:
            justifications.append(
                "Atenção: Nenhum arquivo de teste automatizado dedicado foi detectado para este componente (risco elevado de regressão silenciosa)."
            )

        return ImpactAnalysisResponse(
            repository_id=repo_id,
            target=clean_target,
            resolved_file_path=resolved_file,
            resolved_symbol_name=resolved_sym_name,
            risk_level=risk_level,
            impact_score=min(100, impact_score),
            confirmed_dependents=confirmed_deps[:30],
            inferred_dependents=inferred_deps[:30],
            direct_affected_files=direct_files,
            transitive_affected_files=transitive_files,
            related_test_files=sorted(set(related_tests)),
            technical_justifications=justifications,
        )

    async def generate_architecture_report(
        self, repo_id: uuid.UUID
    ) -> RepositoryArchitectureReportResponse:
        repo = await RepositoryService(self.db).get_repository(repo_id)
        graph_data = await GraphService(self.db).get_repository_graph(
            repo_id=repo_id, scope="file"
        )

        smells: list[ArchitecturalSmellDTO] = []
        for cycle in graph_data.circular_dependencies[:5]:
            smells.append(
                ArchitecturalSmellDTO(
                    smell_type="CIRCULAR_DEPENDENCY",
                    severity="HIGH",
                    component=" -> ".join(cycle),
                    description="Ciclo de dependência direta/indireta detectado entre módulos.",
                    recommendation="Introduza inversão de dependência (interfaces/abstrações) ou extraia um módulo compartilhado.",
                )
            )

        for comp in graph_data.top_coupled_components[:5]:
            if comp.fan_in + comp.fan_out >= 8:
                smells.append(
                    ArchitecturalSmellDTO(
                        smell_type="HIGH_COUPLING_HUB",
                        severity="MEDIUM" if comp.instability < 0.7 else "HIGH",
                        component=comp.file_path,
                        description=f"Módulo concentra Fan-In={comp.fan_in} e Fan-Out={comp.fan_out} (Instabilidade I={comp.instability}).",
                        recommendation="Divida responsabilidades seguindo o Princípio da Responsabilidade Única (SRP) e reduza imports diretos.",
                    )
                )

        suggestions = [
            "Priorize testes unitários e de contrato nos componentes com maior Fan-In listados nos Componentes Críticos.",
            "Utilize a Análise de Impacto antes de alterar assinaturas públicas de funções com relações HIGH_AST.",
        ]
        if graph_data.cycles_count > 0:
            suggestions.insert(
                0,
                f"Elimine as {graph_data.cycles_count} dependência(s) circular(es) identificadas para facilitar manutenção e builds incrementais.",
            )

        overview = (
            f"O repositório **{repo.name}** contém {repo.total_files} arquivos analisados, "
            f"{repo.total_symbols} símbolos estruturais extraídos via Tree-sitter e "
            f"{repo.total_dependencies} relacionamentos mapeados."
        )

        return RepositoryArchitectureReportResponse(
            repository_id=repo.id,
            repository_name=repo.name,
            overview=overview,
            languages_breakdown=repo.languages_stats,
            total_files=repo.total_files,
            total_symbols=repo.total_symbols,
            total_relationships=repo.total_dependencies,
            entry_points=graph_data.entry_points,
            critical_components=graph_data.top_coupled_components[:8],
            architectural_smells=smells,
            improvement_suggestions=suggestions,
        )
