import io
import zipfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.database.session import init_database
from app.main import app
from app.repositories.scanner import RepositoryScanner


def test_scanner_filters_gitignore_and_sensitive_files(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("ignored_dir/\n*.log\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET_KEY=12345", encoding="utf-8")
    (tmp_path / ".env.example").write_text("SECRET_KEY=example", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (src_dir / "app.ts").write_text("export const x: number = 1;\n", encoding="utf-8")

    node_modules = tmp_path / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "index.js").write_text("console.log('ignored');", encoding="utf-8")

    ignored_dir = tmp_path / "ignored_dir"
    ignored_dir.mkdir()
    (ignored_dir / "skip.py").write_text("x = 1", encoding="utf-8")

    scanner = RepositoryScanner(tmp_path)
    results = scanner.scan()
    paths = {r.relative_path for r in results}

    assert "src/main.py" in paths
    assert "src/app.ts" in paths
    assert ".env" not in paths
    assert "node_modules/pkg/index.js" not in paths
    assert "ignored_dir/skip.py" not in paths


@pytest.mark.asyncio
async def test_zip_upload_and_file_explorer_lifecycle():
    await init_database()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app/service.py", "class AuthService:\n    def login(self):\n        return True\n")
        zf.writestr("web/index.ts", "export function boot() { return 'ok'; }\n")
        zf.writestr(".env", "DB_PASSWORD=super_secret")
    zip_buffer.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("demo-project.zip", zip_buffer.getvalue(), "application/zip")}
        data = {"name": "demo-project"}
        create_resp = await client.post("/api/v1/repositories/upload", files=files, data=data)
        assert create_resp.status_code == 201
        repo = create_resp.json()
        repo_id = repo["id"]

        assert repo["name"] == "demo-project"
        assert repo["total_files"] == 2
        assert repo["languages_stats"]["Python"] == 1
        assert repo["languages_stats"]["TypeScript"] == 1

        files_resp = await client.get(f"/api/v1/repositories/{repo_id}/files")
        assert files_resp.status_code == 200
        file_list = files_resp.json()
        assert len(file_list) == 2

        content_resp = await client.get(
            f"/api/v1/repositories/{repo_id}/files/content",
            params={"path": "app/service.py"},
        )
        assert content_resp.status_code == 200
        assert "class AuthService:" in content_resp.json()["content"]

        sync_resp = await client.post(f"/api/v1/repositories/{repo_id}/sync")
        assert sync_resp.status_code == 200
        assert sync_resp.json()["unchanged_files"] == 2

        del_resp = await client.delete(f"/api/v1/repositories/{repo_id}")
        assert del_resp.status_code == 204
