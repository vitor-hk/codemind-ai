import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.schemas import (
    ChatMessageResponse,
    ChatQueryRequest,
    CodeCitationDTO,
)
from app.impact.impact_engine import ImpactAnalysisService
from app.infrastructure.database.models import ChatMessageModel
from app.llm.provider import BaseLLMProvider, OllamaLLMProvider
from app.services.graph_service import GraphService
from app.services.repository_service import RepositoryService
from app.services.semantic_search_service import SemanticSearchService


class GraphRAGEngine:
    """Motor RAG especializado em Engenharia de Software combinando pgvector, FTS e Grafo AST."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: BaseLLMProvider | None = None,
    ) -> None:
        self.db = db
        self.llm = llm_provider or OllamaLLMProvider()

    @staticmethod
    def classify_intent(question: str) -> str:
        q = question.lower()
        if any(w in q for w in ("impacto", "afeta", "afetado", "alterar", "modificar", "quebrar", "mudar")):
            return "IMPACT_ANALYSIS"
        if any(w in q for w in ("arquitetura", "visão geral", "estrutura", "módulos", "acoplamento", "ciclo")):
            return "ARCHITECTURE_OVERVIEW"
        if any(w in q for w in ("fluxo", "execução", "como funciona", "autenticação", "chamada")):
            return "EXECUTION_FLOW"
        return "IMPLEMENTATION_LOOKUP"

    async def ask_repository(
        self, repo_id: uuid.UUID, payload: ChatQueryRequest
    ) -> ChatMessageResponse:
        repo = await RepositoryService(self.db).get_repository(repo_id)
        intent = self.classify_intent(payload.question)

        user_msg = ChatMessageModel(
            repository_id=repo.id,
            role="user",
            intent=intent,
            content=payload.question,
            citations=[],
            execution_metrics={},
        )
        self.db.add(user_msg)
        await self.db.flush()

        search_service = SemanticSearchService(self.db)
        search_res = await search_service.hybrid_search(
            repo_id=repo.id, query=payload.question, limit=4
        )

        citations: list[CodeCitationDTO] = []
        context_blocks: list[str] = [
            f"REPOSITÓRIO: {repo.name} | INTENÇÃO DETECTADA: {intent} | LINGUAGENS: {repo.languages_stats}"
        ]

        if intent in ("ARCHITECTURE_OVERVIEW", "IMPACT_ANALYSIS"):
            graph_info = await GraphService(self.db).get_repository_graph(
                repo_id=repo.id, scope="file", max_nodes=30
            )
            top_hubs = ", ".join(
                f"{c.file_path} (FanIn={c.fan_in}, FanOut={c.fan_out})"
                for c in graph_info.top_coupled_components[:5]
            )
            context_blocks.append(
                f"RESUMO DO GRAFO DE ARQUITETURA:\n"
                f"- Pontos de Entrada: {', '.join(graph_info.entry_points[:8]) or 'N/A'}\n"
                f"- Componentes Críticos (Maior Acoplamento): {top_hubs or 'N/A'}\n"
                f"- Ciclos Detectados: {graph_info.cycles_count}"
            )

        if intent == "IMPACT_ANALYSIS" and search_res.results:
            top_symbol = search_res.results[0].symbol_name.split(" (part")[0]
            impact = await ImpactAnalysisService(self.db).analyze_change_impact(
                repo.id, top_symbol
            )
            context_blocks.append(
                f"RELATÓRIO DE IMPACTO ESTÁTICO PARA `{top_symbol}` ({impact.resolved_file_path}):\n"
                f"- Risco Estimado: {impact.risk_level} (Score: {impact.impact_score}/100)\n"
                f"- Arquivos Diretamente Afetados: {', '.join(impact.direct_affected_files) or 'Nenhum'}\n"
                f"- Arquivos Transitivamente Afetados: {', '.join(impact.transitive_affected_files) or 'Nenhum'}\n"
                f"- Testes Relacionados: {', '.join(impact.related_test_files) or 'Nenhum detectado'}"
            )

        for idx, hit in enumerate(search_res.results, start=1):
            numbered_lines = "\n".join(
                f"{hit.start_line + i}: {line}"
                for i, line in enumerate(hit.raw_code.splitlines()[:20])
            )
            context_blocks.append(
                f"[EVIDÊNCIA #{idx}] Arquivo: `{hit.file_path}:L{hit.start_line}-L{hit.end_line}` | "
                f"Símbolo: `{hit.symbol_name}` | Assinatura: `{hit.signature}`\n"
                f"```\n{numbered_lines}\n```"
            )
            citations.append(
                CodeCitationDTO(
                    file_path=hit.file_path,
                    symbol_name=hit.symbol_name,
                    start_line=hit.start_line,
                    end_line=hit.end_line,
                    signature=hit.signature,
                    snippet="\n".join(hit.raw_code.splitlines()[:8]),
                )
            )

        grounded_context = "\n\n".join(context_blocks)
        llm_res = await self.llm.generate(
            user_question=payload.question,
            grounded_context=grounded_context,
            model_name=payload.model_name,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )

        metrics = {
            "model_used": llm_res.model_used,
            "latency_ms": llm_res.latency_ms,
            "chunks_retrieved": len(search_res.results),
            "intent": intent,
            "used_fallback": llm_res.used_fallback,
        }

        assistant_msg = ChatMessageModel(
            repository_id=repo.id,
            role="assistant",
            intent=intent,
            content=llm_res.answer,
            citations=[c.model_dump() for c in citations],
            execution_metrics=metrics,
        )
        self.db.add(assistant_msg)
        await self.db.commit()
        await self.db.refresh(assistant_msg)

        return ChatMessageResponse.model_validate(assistant_msg)

    async def list_chat_history(self, repo_id: uuid.UUID) -> list[ChatMessageResponse]:
        await RepositoryService(self.db).get_repository(repo_id)
        stmt = (
            select(ChatMessageModel)
            .where(ChatMessageModel.repository_id == repo_id)
            .order_by(ChatMessageModel.created_at.asc())
        )
        res = await self.db.execute(stmt)
        messages = list(res.scalars().all())
        return [ChatMessageResponse.model_validate(m) for m in messages]
