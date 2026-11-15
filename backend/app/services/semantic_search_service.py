import re
import uuid
from pathlib import Path
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.schemas import (
    HybridSearchResponse,
    IndexingSummaryResponse,
    SearchChunkHitDTO,
)
from app.embeddings.chunker import ASTSmartChunker, SmartCodeChunkDTO
from app.embeddings.provider import BaseEmbeddingProvider, OllamaEmbeddingProvider
from app.infrastructure.database.models import (
    CodeChunkModel,
    CodeSymbolModel,
    RepositoryFileModel,
    RepositoryModel,
)

logger = get_logger(__name__)
settings = get_settings()
chunker = ASTSmartChunker()

EMBED_BATCH_SIZE = 32
RRF_K = 60


class SemanticSearchService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = embedding_provider or OllamaEmbeddingProvider()

    async def index_repository(self, repo_id: uuid.UUID) -> IndexingSummaryResponse:
        repo_res = await self.db.execute(
            select(RepositoryModel).where(RepositoryModel.id == repo_id)
        )
        repo = repo_res.scalar_one_or_none()
        if not repo:
            raise ValueError("Repositório não encontrado para indexação semântica.")

        existing_res = await self.db.execute(
            select(CodeChunkModel).where(CodeChunkModel.repository_id == repo_id)
        )
        existing_chunks = list(existing_res.scalars().all())
        existing_vectors_by_hash: dict[str, list[float]] = {
            c.content_hash: list(c.embedding) for c in existing_chunks
        }

        files_res = await self.db.execute(
            select(RepositoryFileModel).where(RepositoryFileModel.repository_id == repo_id)
        )
        files = list(files_res.scalars().all())

        syms_res = await self.db.execute(
            select(CodeSymbolModel)
            .where(CodeSymbolModel.repository_id == repo_id)
            .order_by(CodeSymbolModel.start_line.asc())
        )
        all_symbols = list(syms_res.scalars().all())
        symbols_by_file: dict[uuid.UUID, list[CodeSymbolModel]] = {}
        for s in all_symbols:
            symbols_by_file.setdefault(s.file_id, []).append(s)

        root_path = Path(repo.local_path).resolve()
        planned_chunks: list[SmartCodeChunkDTO] = []

        for f_model in files:
            abs_path = (root_path / f_model.relative_path).resolve()
            if not abs_path.is_file():
                continue
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            file_syms = symbols_by_file.get(f_model.id, [])
            planned_chunks.extend(chunker.chunk_file(f_model, content, file_syms))

        to_embed_dtos: list[SmartCodeChunkDTO] = []
        for dto in planned_chunks:
            if dto.content_hash not in existing_vectors_by_hash:
                to_embed_dtos.append(dto)

        newly_embedded = len(to_embed_dtos)
        reused_count = len(planned_chunks) - newly_embedded

        new_vectors_by_hash: dict[str, list[float]] = {}
        for i in range(0, len(to_embed_dtos), EMBED_BATCH_SIZE):
            batch = to_embed_dtos[i : i + EMBED_BATCH_SIZE]
            texts = [b.contextual_content for b in batch]
            vectors = await self.provider.embed_texts(texts)
            for dto, vec in zip(batch, vectors):
                new_vectors_by_hash[dto.content_hash] = vec

        await self.db.execute(
            delete(CodeChunkModel).where(CodeChunkModel.repository_id == repo_id)
        )
        await self.db.flush()

        for dto in planned_chunks:
            vec = (
                existing_vectors_by_hash.get(dto.content_hash)
                or new_vectors_by_hash.get(dto.content_hash)
            )
            if not vec:
                continue
            self.db.add(
                CodeChunkModel(
                    repository_id=repo.id,
                    file_id=dto.file_id,
                    symbol_id=dto.symbol_id,
                    file_path=dto.file_path,
                    language=dto.language,
                    class_name=dto.class_name,
                    symbol_name=dto.symbol_name,
                    element_type=dto.element_type,
                    signature=dto.signature,
                    start_line=dto.start_line,
                    end_line=dto.end_line,
                    content_hash=dto.content_hash,
                    contextual_content=dto.contextual_content,
                    raw_code=dto.raw_code,
                    embedding=vec,
                )
            )

        repo.total_chunks = len(planned_chunks)
        await self.db.commit()

        logger.info(
            "repository_semantic_indexed",
            repo_id=str(repo.id),
            total_chunks=len(planned_chunks),
            newly_embedded=newly_embedded,
            reused=reused_count,
        )

        return IndexingSummaryResponse(
            repository_id=repo.id,
            total_chunks=len(planned_chunks),
            newly_embedded=newly_embedded,
            reused_cached_chunks=reused_count,
            embedding_model=settings.OLLAMA_EMBED_MODEL,
        )

    async def hybrid_search(
        self,
        repo_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> HybridSearchResponse:
        clean_query = query.strip()
        if not clean_query:
            return HybridSearchResponse(
                repository_id=repo_id, query=query, total_hits=0, results=[]
            )

        count_res = await self.db.execute(
            select(func.count(CodeChunkModel.id)).where(
                CodeChunkModel.repository_id == repo_id
            )
        )
        chunk_count = count_res.scalar_one() or 0
        if chunk_count == 0:
            await self.index_repository(repo_id)

        query_vec = await self.provider.embed_query(clean_query)
        vec_stmt = (
            select(CodeChunkModel)
            .where(CodeChunkModel.repository_id == repo_id)
            .order_by(CodeChunkModel.embedding.cosine_distance(query_vec))
            .limit(30)
        )
        vec_res = await self.db.execute(vec_stmt)
        vector_hits = list(vec_res.scalars().all())

        tokens = [
            t.lower()
            for t in re.split(r"[^a-zA-Z0-9_]+", clean_query)
            if len(t) >= 2
        ]

        fts_vector = func.to_tsvector("simple", CodeChunkModel.contextual_content)
        fts_query = func.websearch_to_tsquery("simple", clean_query)

        token_filters = [fts_vector.op("@@")(fts_query)]
        for tok in tokens[:5]:
            token_filters.append(CodeChunkModel.symbol_name.ilike(f"%{tok}%"))
            token_filters.append(CodeChunkModel.signature.ilike(f"%{tok}%"))
            token_filters.append(CodeChunkModel.raw_code.ilike(f"%{tok}%"))

        lex_stmt = (
            select(CodeChunkModel)
            .where(
                CodeChunkModel.repository_id == repo_id,
                or_(*token_filters),
            )
            .order_by(func.ts_rank_cd(fts_vector, fts_query).desc())
            .limit(30)
        )
        lex_res = await self.db.execute(lex_stmt)
        lexical_hits = list(lex_res.scalars().all())

        chunks_by_id: dict[uuid.UUID, CodeChunkModel] = {}
        vector_ranks: dict[uuid.UUID, int] = {}
        lexical_ranks: dict[uuid.UUID, int] = {}

        for rank, chunk in enumerate(vector_hits, start=1):
            chunks_by_id[chunk.id] = chunk
            vector_ranks[chunk.id] = rank

        for rank, chunk in enumerate(lexical_hits, start=1):
            chunks_by_id[chunk.id] = chunk
            lexical_ranks[chunk.id] = rank

        scored_hits: list[SearchChunkHitDTO] = []

        for chunk_id, chunk in chunks_by_id.items():
            v_rank = vector_ranks.get(chunk_id)
            l_rank = lexical_ranks.get(chunk_id)

            rrf_score = 0.0
            reasons: list[str] = []

            if v_rank is not None:
                rrf_score += 1.0 / (RRF_K + v_rank)
                reasons.append(f"semantic_vector (#{v_rank})")

            if l_rank is not None:
                rrf_score += 1.0 / (RRF_K + l_rank)
                reasons.append(f"lexical_fts (#{l_rank})")

            rerank_boost = 0.0
            sym_lower = chunk.symbol_name.lower()
            sig_lower = chunk.signature.lower()
            code_lower = chunk.raw_code.lower()

            for tok in tokens:
                if tok == sym_lower or tok in sym_lower.split("."):
                    rerank_boost += 0.035
                    if "exact_symbol_match" not in reasons:
                        reasons.append("exact_symbol_match")
                elif tok in sig_lower:
                    rerank_boost += 0.020
                    if "signature_match" not in reasons:
                        reasons.append("signature_match")
                elif tok in code_lower:
                    rerank_boost += 0.008

            final_score = round(rrf_score + rerank_boost, 5)

            scored_hits.append(
                SearchChunkHitDTO(
                    chunk_id=chunk.id,
                    symbol_id=chunk.symbol_id,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    class_name=chunk.class_name,
                    symbol_name=chunk.symbol_name,
                    element_type=chunk.element_type,
                    signature=chunk.signature,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    raw_code=chunk.raw_code,
                    rrf_score=round(rrf_score, 5),
                    rerank_score=final_score,
                    vector_rank=v_rank,
                    lexical_rank=l_rank,
                    match_reasons=reasons,
                )
            )

        scored_hits.sort(key=lambda item: item.rerank_score, reverse=True)
        top_results = scored_hits[:limit]

        return HybridSearchResponse(
            repository_id=repo_id,
            query=clean_query,
            total_hits=len(top_results),
            results=top_results,
        )
