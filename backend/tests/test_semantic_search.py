import io
import zipfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_smart_chunking_pgvector_and_hybrid_search():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app/billing.py",
            '''class BillingEngine:
    """Calculates invoice total with taxes and discounts."""
    def calculate_invoice_total(self, subtotal: float, tax_rate: float) -> float:
        tax_amount = subtotal * tax_rate
        return subtotal + tax_amount
''',
        )
        zf.writestr(
            "app/security.py",
            '''class TokenValidator:
    """Validates JWT tokens and user permissions."""
    def verify_jwt_signature(self, token: str) -> bool:
        return token.startswith("eyJ")
''',
        )
    zip_buffer.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("search-demo.zip", zip_buffer.getvalue(), "application/zip")}
        resp = await client.post(
            "/api/v1/repositories/upload", files=files, data={"name": "search-demo"}
        )
        assert resp.status_code == 201
        repo = resp.json()
        repo_id = repo["id"]
        assert repo["total_chunks"] >= 2

        idx_resp = await client.post(f"/api/v1/repositories/{repo_id}/index")
        assert idx_resp.status_code == 200
        idx_data = idx_resp.json()
        assert idx_data["reused_cached_chunks"] == idx_data["total_chunks"]
        assert idx_data["newly_embedded"] == 0

        search_resp = await client.get(
            f"/api/v1/repositories/{repo_id}/search",
            params={"q": "calculate invoice total tax", "limit": 5},
        )
        assert search_resp.status_code == 200
        s_data = search_resp.json()
        assert s_data["total_hits"] >= 1
        top_hit = s_data["results"][0]
        assert top_hit["file_path"] == "app/billing.py"
        assert "calculate_invoice_total" in top_hit["symbol_name"]

        await client.delete(f"/api/v1/repositories/{repo_id}")
