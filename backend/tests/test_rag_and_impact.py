import io
import zipfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_impact_analysis_and_architecture_report():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app/payment.py",
            '''class PaymentGateway:
    """Processes credit card payments."""
    def process_payment(self, amount: float) -> bool:
        return amount > 0
''',
        )
        zf.writestr(
            "app/checkout.py",
            '''from app.payment import PaymentGateway

class CheckoutService:
    def complete_order(self, total: float) -> bool:
        return process_payment(total)
''',
        )
        zf.writestr(
            "tests/test_payment.py",
            '''from app.payment import PaymentGateway

def test_process_payment_positive():
    assert process_payment(100.0) is True
''',
        )
    zip_buffer.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("impact-demo.zip", zip_buffer.getvalue(), "application/zip")}
        resp = await client.post(
            "/api/v1/repositories/upload", files=files, data={"name": "impact-demo"}
        )
        assert resp.status_code == 201
        repo_id = resp.json()["id"]

        imp_resp = await client.get(
            f"/api/v1/repositories/{repo_id}/impact",
            params={"target": "process_payment"},
        )
        assert imp_resp.status_code == 200
        imp_data = imp_resp.json()
        assert imp_data["resolved_file_path"] == "app/payment.py"
        assert "app/checkout.py" in imp_data["direct_affected_files"]
        assert "tests/test_payment.py" in imp_data["related_test_files"]
        assert imp_data["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")

        rep_resp = await client.get(f"/api/v1/repositories/{repo_id}/report")
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert rep_data["repository_name"] == "impact-demo"
        assert rep_data["total_files"] == 3

        chat_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/chat",
            json={
                "question": "Se eu alterar process_payment, quais arquivos são afetados?",
                "max_tokens": 250,
            },
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert chat_data["intent"] == "IMPACT_ANALYSIS"
        assert len(chat_data["citations"]) >= 1
        assert any(c["file_path"] == "app/payment.py" for c in chat_data["citations"])

        hist_resp = await client.get(f"/api/v1/repositories/{repo_id}/chat/history")
        assert hist_resp.status_code == 200
        assert len(hist_resp.json()) == 2

        await client.delete(f"/api/v1/repositories/{repo_id}")
