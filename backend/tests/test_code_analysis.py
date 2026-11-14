import io
import zipfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.analyzers.tree_sitter_engine import TreeSitterAnalyzerEngine
from app.main import app


def test_tree_sitter_multi_language_extraction():
    engine = TreeSitterAnalyzerEngine()

    py_code = '''
from app.db import UserRepository

class BaseService:
    pass

class AuthService(BaseService):
    """Handles user authentication."""
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def authenticate_user(self, email: str, password: str) -> bool:
        user = self.verify_credentials(email, password)
        return user

    def verify_credentials(self, email: str, password: str) -> bool:
        return True
'''
    py_res = engine.analyze_file("app/services/auth.py", "Python", py_code)
    py_names = {s.qualified_name: s for s in py_res.symbols}

    assert "AuthService" in py_names
    assert py_names["AuthService"].bases == ["BaseService"]
    assert py_names["AuthService"].documentation == "Handles user authentication."
    assert "AuthService.__init__" in py_names
    assert py_names["AuthService.__init__"].symbol_type.value == "constructor"
    assert "AuthService.authenticate_user" in py_names
    assert any(c[0] == "verify_credentials" for c in py_names["AuthService.authenticate_user"].calls)

    ts_code = '''
import { ApiClient } from "./api";

export interface UserDTO {
  id: string;
}

export class UserController extends BaseController {
  constructor(private api: ApiClient) {
    super();
  }
  async fetchProfile(id: string): Promise<UserDTO> {
    return this.loadFromApi(id);
  }
}
'''
    ts_res = engine.analyze_file("src/user.controller.ts", "TypeScript", ts_code)
    ts_names = {s.qualified_name: s for s in ts_res.symbols}
    assert "UserDTO" in ts_names
    assert ts_names["UserDTO"].symbol_type.value == "interface"
    assert "UserController" in ts_names
    assert "UserController.fetchProfile" in ts_names

    java_code = '''
import com.codemind.repo.OrderRepository;

public class OrderService extends BaseOrderService {
    public OrderService() {}
    public void processOrder(String orderId) {
        validateOrder(orderId);
    }
    private void validateOrder(String orderId) {}
}
'''
    java_res = engine.analyze_file("src/OrderService.java", "Java", java_code)
    java_names = {s.qualified_name: s for s in java_res.symbols}
    assert "OrderService" in java_names
    assert "OrderService.processOrder" in java_names


@pytest.mark.asyncio
async def test_ast_pipeline_persists_symbols_and_relationships():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app/repo.py",
            "class UserRepository:\n    def find_by_email(self, email: str):\n        return email\n",
        )
        zf.writestr(
            "app/auth.py",
            "from app.repo import UserRepository\n\nclass AuthService:\n    def login(self, email: str):\n        return find_by_email(email)\n",
        )
    zip_buffer.seek(0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("ast-demo.zip", zip_buffer.getvalue(), "application/zip")}
        resp = await client.post("/api/v1/repositories/upload", files=files, data={"name": "ast-demo"})
        assert resp.status_code == 201
        repo = resp.json()
        repo_id = repo["id"]

        assert repo["total_symbols"] >= 4
        assert repo["total_dependencies"] >= 2

        sym_resp = await client.get(f"/api/v1/repositories/{repo_id}/symbols")
        assert sym_resp.status_code == 200
        symbols = sym_resp.json()
        qualified_names = {s["qualified_name"] for s in symbols}
        assert "UserRepository" in qualified_names
        assert "UserRepository.find_by_email" in qualified_names
        assert "AuthService.login" in qualified_names

        rel_resp = await client.get(f"/api/v1/repositories/{repo_id}/relationships")
        assert rel_resp.status_code == 200
        rels = rel_resp.json()
        rel_types = {r["relation_type"] for r in rels}
        assert "IMPORTS" in rel_types
        assert "CALLS" in rel_types

        await client.delete(f"/api/v1/repositories/{repo_id}")
