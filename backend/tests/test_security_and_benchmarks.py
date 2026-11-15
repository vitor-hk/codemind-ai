import io
import zipfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.database.session import AsyncSessionLocal
from app.main import app
from app.rag.evaluator import GoldenQueryCase, RAGEvaluator


@pytest.mark.asyncio
async def test_security_zip_slip_path_traversal_blocked():
    malicious_zip = io.BytesIO()
    with zipfile.ZipFile(malicious_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../../etc/evil_traversal.py", "import os\n")
    malicious_zip.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("malicious.zip", malicious_zip.getvalue(), "application/zip")}
        resp = await client.post("/api/v1/repositories/upload", files=files)
        assert resp.status_code == 400
        assert "Caminho inseguro" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_incremental_indexing_and_rag_benchmark_metrics():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app/auth_service.py",
            '''class AuthService:
    """Handles JWT authentication and password hashing."""
    def authenticate_user(self, email: str, password: str) -> str:
        return "jwt_token_signed"
''',
        )
        zf.writestr(
            "app/payment_processor.ts",
            '''export class PaymentProcessor {
  calculateOrderTotal(subtotal: number, discount: number): number {
    return subtotal - discount;
  }
}
''',
        )
        zf.writestr(
            "app/InventoryManager.java",
            '''public class InventoryManager {
    public boolean reserveStockItem(String sku, int quantity) {
        return quantity > 0;
    }
}
''',
        )
    zip_buffer.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("polyglot-benchmark.zip", zip_buffer.getvalue(), "application/zip")}
        resp = await client.post(
            "/api/v1/repositories/upload",
            files=files,
            data={"name": "polyglot-benchmark"},
        )
        assert resp.status_code == 201
        repo = resp.json()
        repo_id = repo["id"]

        golden_suite = [
            GoldenQueryCase(
                question="authenticate user JWT password login",
                expected_files={"app/auth_service.py"},
                expected_symbols={"AuthService.authenticate_user"},
            ),
            GoldenQueryCase(
                question="calculate order total subtotal discount",
                expected_files={"app/payment_processor.ts"},
                expected_symbols={"PaymentProcessor.calculateOrderTotal"},
            ),
            GoldenQueryCase(
                question="reserve stock item inventory sku quantity",
                expected_files={"app/InventoryManager.java"},
                expected_symbols={"InventoryManager.reserveStockItem"},
            ),
        ]

        import uuid
        async with AsyncSessionLocal() as session:
            summary = await RAGEvaluator.run_suite(
                db=session,
                repo_id=uuid.UUID(repo_id),
                golden_cases=golden_suite,
                k=3,
            )

        assert summary.mean_recall_at_k >= 0.99
        assert summary.mrr >= 0.80
        assert summary.mean_ndcg_at_k >= 0.80

        bench_dir = Path("../docs/benchmarks")
        bench_dir.mkdir(parents=True, exist_ok=True)
        report_lines = [
            "# CodeMind AI — Benchmark de Qualidade de Recuperação Híbrida (Graph-RAG)",
            "",
            f"- **Top-K avaliado:** K={summary.k}",
            f"- **Total de Consultas Técnicas (Polyglot: Python, TypeScript, Java):** {summary.total_queries}",
            f"- **Mean Recall@{summary.k}:** `{summary.mean_recall_at_k:.2%}`",
            f"- **Mean Precision@{summary.k}:** `{summary.mean_precision_at_k:.2%}`",
            f"- **MRR (Mean Reciprocal Rank):** `{summary.mrr:.4f}`",
            f"- **Mean NDCG@{summary.k}:** `{summary.mean_ndcg_at_k:.4f}`",
            f"- **Latência Média de Recuperação Híbrida:** `{summary.mean_latency_ms} ms`",
            "",
            "| Consulta Técnica | Arquivos Recuperados (Top-K) | Recall@3 | RR | NDCG@3 | Latência (ms) |",
            "| :--- | :--- | :---: | :---: | :---: | :---: |",
        ]
        for c in summary.cases:
            files_str = ", ".join(f"`{f}`" for f in c.retrieved_files)
            report_lines.append(
                f"| {c.question} | {files_str} | {c.recall_at_k:.2f} | {c.reciprocal_rank:.2f} | {c.ndcg_at_k:.2f} | {c.latency_ms} |"
            )

        (bench_dir / "BENCHMARK_RESULTS.md").write_text(
            "\n".join(report_lines) + "\n", encoding="utf-8"
        )

        await client.delete(f"/api/v1/repositories/{repo_id}")
