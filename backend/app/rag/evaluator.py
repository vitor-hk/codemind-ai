import math
import time
import uuid
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.semantic_search_service import SemanticSearchService


@dataclass
class GoldenQueryCase:
    question: str
    expected_files: set[str]
    expected_symbols: set[str]


@dataclass
class QueryEvaluationResult:
    question: str
    retrieved_files: list[str]
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float
    latency_ms: float


@dataclass
class BenchmarkSuiteSummary:
    k: int
    total_queries: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr: float
    mean_ndcg_at_k: float
    mean_latency_ms: float
    cases: list[QueryEvaluationResult]


class RAGEvaluator:
    """Calcula métricas clássicas de Information Retrieval (Precision@K, Recall@K, MRR, NDCG@K)."""

    @staticmethod
    def compute_metrics(
        retrieved_files: list[str],
        expected_files: set[str],
        k: int,
    ) -> tuple[float, float, float, float]:
        top_k: list[str] = []
        for f in retrieved_files:
            if f not in top_k:
                top_k.append(f)
            if len(top_k) == k:
                break

        if not top_k or not expected_files:
            return 0.0, 0.0, 0.0, 0.0

        hits = [1 if f in expected_files else 0 for f in top_k]
        relevant_found = sum(hits)

        precision = round(relevant_found / len(top_k), 4)
        recall = round(relevant_found / len(expected_files), 4)

        rr = 0.0
        for idx, is_hit in enumerate(hits, start=1):
            if is_hit:
                rr = round(1.0 / idx, 4)
                break

        dcg = sum(rel / math.log2(idx + 1) for idx, rel in enumerate(hits, start=1))
        ideal_hits = [1] * min(len(expected_files), k)
        idcg = sum(rel / math.log2(idx + 1) for idx, rel in enumerate(ideal_hits, start=1))
        ndcg = round(dcg / idcg, 4) if idcg > 0 else 0.0

        return precision, recall, rr, ndcg

    @classmethod
    async def run_suite(
        cls,
        db: AsyncSession,
        repo_id: uuid.UUID,
        golden_cases: list[GoldenQueryCase],
        k: int = 3,
    ) -> BenchmarkSuiteSummary:
        search_service = SemanticSearchService(db)
        results: list[QueryEvaluationResult] = []

        for case in golden_cases:
            t0 = time.perf_counter()
            search_res = await search_service.hybrid_search(
                repo_id=repo_id, query=case.question, limit=k * 2
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

            retrieved_files = [hit.file_path for hit in search_res.results]
            p_k, r_k, rr, ndcg = cls.compute_metrics(
                retrieved_files=retrieved_files,
                expected_files=case.expected_files,
                k=k,
            )
            results.append(
                QueryEvaluationResult(
                    question=case.question,
                    retrieved_files=retrieved_files[:k],
                    precision_at_k=p_k,
                    recall_at_k=r_k,
                    reciprocal_rank=rr,
                    ndcg_at_k=ndcg,
                    latency_ms=elapsed_ms,
                )
            )

        n = len(results) or 1
        return BenchmarkSuiteSummary(
            k=k,
            total_queries=len(results),
            mean_precision_at_k=round(sum(r.precision_at_k for r in results) / n, 4),
            mean_recall_at_k=round(sum(r.recall_at_k for r in results) / n, 4),
            mrr=round(sum(r.reciprocal_rank for r in results) / n, 4),
            mean_ndcg_at_k=round(sum(r.ndcg_at_k for r in results) / n, 4),
            mean_latency_ms=round(sum(r.latency_ms for r in results) / n, 2),
            cases=results,
        )
