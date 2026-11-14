import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_structure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["app_name"] == "CodeMind AI"
    assert "database" in payload
    assert "redis" in payload
    assert "ollama" in payload
    assert payload["database"]["details"]["pgvector_installed"] is True