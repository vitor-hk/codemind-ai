import io
import zipfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_dependency_graph_cycles_and_transitive_neighborhood():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app/db.py",
            "class Database:\n    def query(self):\n        return []\n",
        )
        zf.writestr(
            "app/repository.py",
            "from app.db import Database\n\nclass UserRepository:\n    def get_users(self):\n        return query()\n",
        )
        zf.writestr(
            "app/service.py",
            "from app.repository import UserRepository\n\nclass UserService:\n    def list_all(self):\n        return get_users()\n",
        )
        zf.writestr(
            "app/controller.py",
            "from app.service import UserService\n\nclass UserController:\n    def endpoint(self):\n        return list_all()\n",
        )
    zip_buffer.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("graph-demo.zip", zip_buffer.getvalue(), "application/zip")}
        resp = await client.post(
            "/api/v1/repositories/upload", files=files, data={"name": "graph-demo"}
        )
        assert resp.status_code == 201
        repo_id = resp.json()["id"]

        graph_resp = await client.get(
            f"/api/v1/repositories/{repo_id}/graph", params={"scope": "file"}
        )
        assert graph_resp.status_code == 200
        g_data = graph_resp.json()

        assert g_data["total_nodes"] == 4
        assert g_data["total_edges"] >= 3
        assert "app/controller.py" in g_data["entry_points"]

        neigh_resp = await client.get(
            f"/api/v1/repositories/{repo_id}/graph/neighborhood",
            params={"node_id": "app/db.py", "scope": "file"},
        )
        assert neigh_resp.status_code == 200
        n_data = neigh_resp.json()
        assert "app/repository.py" in n_data["direct_dependents"]
        assert "app/service.py" in n_data["transitive_dependents"]
        assert "app/controller.py" in n_data["transitive_dependents"]

        await client.delete(f"/api/v1/repositories/{repo_id}")
