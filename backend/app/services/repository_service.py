from app.services.analysis_service import CodeAnalysisService
import asyncio
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from fastapi import HTTPException, UploadFile, status
from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.enums import AnalysisStatus, SourceType
from app.domain.schemas import GitImportRequest, SyncResultResponse
from app.infrastructure.database.models import RepositoryFileModel, RepositoryModel
from app.repositories.scanner import RepositoryScanner, ScannedFileInfo

logger = get_logger(__name__)
settings = get_settings()

MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 150 * 1024 * 1024  # 150 MB


class RepositoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _extract_repo_name_from_url(git_url: str) -> str:
        parsed = urlparse(git_url)
        name = Path(parsed.path).name
        if name.endswith(".git"):
            name = name[:-4]
        return name or "repository"

    @staticmethod
    def _build_authenticated_url(git_url: str, access_token: str | None) -> str:
        if not access_token:
            return git_url
        parsed = urlparse(git_url)
        netloc = f"x-access-token:{access_token}@{parsed.hostname}"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))

    @staticmethod
    def _clone_git_sync(clone_url: str, target_dir: Path, branch: str | None) -> tuple[str, str]:
        kwargs = {"depth": 1, "single_branch": True}
        if branch:
            kwargs["branch"] = branch
        repo = Repo.clone_from(clone_url, str(target_dir), **kwargs)
        active_branch = repo.active_branch.name if not repo.head.is_detached else (branch or "HEAD")
        commit_hash = repo.head.commit.hexsha
        return active_branch, commit_hash

    @staticmethod
    def _pull_git_sync(local_dir: Path) -> str:
        repo = Repo(str(local_dir))
        origin = repo.remotes.origin
        origin.pull()
        return repo.head.commit.hexsha

    @staticmethod
    def _safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
        """Extrai arquivo ZIP prevenindo ataques Zip Slip e Zip Bomb."""
        target_resolved = target_dir.resolve()
        total_uncompressed = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                total_uncompressed += member.file_size
                if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                    raise ValueError("Arquivo compactado excede o limite de segurança de 150MB.")

                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"Caminho inseguro detectado no ZIP: {member.filename}")

                dest_path = (target_resolved / member_path).resolve()
                if not dest_path.is_relative_to(target_resolved):
                    raise ValueError(f"Tentativa de Path Traversal detectada: {member.filename}")

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as source, open(dest_path, "wb") as target:
                    shutil.copyfileobj(source, target)

        entries = [p for p in target_resolved.iterdir() if p.name != "__MACOSX"]
        if len(entries) == 1 and entries[0].is_dir() and entries[0].name.lower() not in {"app", "src", "lib", "pkg", "core", "backend", "frontend", "tests"}:
            single_root = entries[0]
            for item in single_root.iterdir():
                shutil.move(str(item), str(target_resolved / item.name))
            single_root.rmdir()

    async def import_git_repository(self, payload: GitImportRequest) -> RepositoryModel:
        repo_id = uuid.uuid4()
        clean_url = str(payload.git_url)
        repo_name = payload.name or self._extract_repo_name_from_url(clean_url)
        target_dir = (settings.REPOS_WORKSPACE_DIR / str(repo_id)).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        repo_model = RepositoryModel(
            id=repo_id,
            name=repo_name,
            description=f"Repositório Git importado de {clean_url}",
            source_type=SourceType.GIT_URL,
            source_url=clean_url,
            local_path=str(target_dir),
            default_branch=payload.branch or "main",
            status=AnalysisStatus.PROCESSING,
        )
        self.db.add(repo_model)
        await self.db.flush()

        try:
            auth_url = self._build_authenticated_url(clean_url, payload.access_token)
            branch_name, commit_hash = await asyncio.to_thread(
                self._clone_git_sync, auth_url, target_dir, payload.branch
            )
            repo_model.default_branch = branch_name
            repo_model.last_commit_hash = commit_hash

            await self._scan_and_sync_files(repo_model, target_dir)
            await CodeAnalysisService(self.db).analyze_repository(repo_model.id)
            repo_model.status = AnalysisStatus.COMPLETED
            repo_model.last_analyzed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(repo_model)

            logger.info(
                "git_repository_imported",
                repo_id=str(repo_model.id),
                name=repo_model.name,
                files=repo_model.total_files,
            )
            return repo_model
        except Exception as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            await self.db.rollback()
            logger.error("git_import_failed", url=clean_url, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Falha ao importar repositório Git: {str(exc)}",
            ) from exc

    async def import_zip_repository(self, file: UploadFile, name: str | None = None) -> RepositoryModel:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Envie um arquivo com extensão .zip válido.",
            )

        repo_id = uuid.uuid4()
        repo_name = name or Path(file.filename).stem
        target_dir = (settings.REPOS_WORKSPACE_DIR / str(repo_id)).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        repo_model = RepositoryModel(
            id=repo_id,
            name=repo_name,
            description=f"Projeto importado via arquivo compactado ({file.filename})",
            source_type=SourceType.ZIP_UPLOAD,
            source_url=None,
            local_path=str(target_dir),
            default_branch="archive",
            status=AnalysisStatus.PROCESSING,
        )
        self.db.add(repo_model)
        await self.db.flush()

        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            try:
                await asyncio.to_thread(self._safe_extract_zip, tmp_path, target_dir)
            finally:
                tmp_path.unlink(missing_ok=True)

            await self._scan_and_sync_files(repo_model, target_dir)
            await CodeAnalysisService(self.db).analyze_repository(repo_model.id)
            repo_model.status = AnalysisStatus.COMPLETED
            repo_model.last_analyzed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(repo_model)
            return repo_model
        except Exception as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Falha ao processar arquivo ZIP: {str(exc)}",
            ) from exc

    async def _scan_and_sync_files(
        self, repo_model: RepositoryModel, target_dir: Path
    ) -> tuple[int, int, int, int]:
        scanner = RepositoryScanner(target_dir)
        scanned_files: list[ScannedFileInfo] = await asyncio.to_thread(scanner.scan)

        existing_stmt = select(RepositoryFileModel).where(
            RepositoryFileModel.repository_id == repo_model.id
        )
        existing_res = await self.db.execute(existing_stmt)
        existing_by_path: dict[str, RepositoryFileModel] = {
            f.relative_path: f for f in existing_res.scalars().all()
        }

        scanned_by_path: dict[str, ScannedFileInfo] = {
            item.relative_path: item for item in scanned_files
        }

        added = 0
        modified = 0
        removed = 0
        unchanged = 0
        lang_counts: dict[str, int] = {}

        for rel_path, info in scanned_by_path.items():
            lang_counts[info.language] = lang_counts.get(info.language, 0) + 1
            existing = existing_by_path.get(rel_path)

            if existing is None:
                added += 1
                self.db.add(
                    RepositoryFileModel(
                        repository_id=repo_model.id,
                        relative_path=info.relative_path,
                        language=info.language,
                        extension=info.extension,
                        size_bytes=info.size_bytes,
                        line_count=info.line_count,
                        content_hash=info.content_hash,
                        is_ast_supported=info.is_ast_supported,
                    )
                )
            elif existing.content_hash != info.content_hash:
                modified += 1
                existing.size_bytes = info.size_bytes
                existing.line_count = info.line_count
                existing.content_hash = info.content_hash
                existing.language = info.language
                existing.is_ast_supported = info.is_ast_supported
            else:
                unchanged += 1

        for rel_path, existing_file in existing_by_path.items():
            if rel_path not in scanned_by_path:
                removed += 1
                await self.db.delete(existing_file)

        repo_model.languages_stats = lang_counts
        repo_model.total_files = len(scanned_files)
        return added, modified, removed, unchanged

    async def sync_repository(self, repo_id: uuid.UUID) -> SyncResultResponse:
        repo_model = await self.get_repository(repo_id)
        local_dir = Path(repo_model.local_path)
        if not local_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diretório local do repositório não encontrado no disco.",
            )

        repo_model.status = AnalysisStatus.PROCESSING
        await self.db.flush()

        if repo_model.source_type == SourceType.GIT_URL and (local_dir / ".git").exists():
            try:
                commit_hash = await asyncio.to_thread(self._pull_git_sync, local_dir)
                repo_model.last_commit_hash = commit_hash
            except Exception as exc:
                logger.warning("git_pull_warning", repo_id=str(repo_id), error=str(exc))

        added, modified, removed, unchanged = await self._scan_and_sync_files(
            repo_model, local_dir
        )
        await CodeAnalysisService(self.db).analyze_repository(repo_model.id)
        repo_model.status = AnalysisStatus.COMPLETED
        repo_model.last_analyzed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(repo_model)

        return SyncResultResponse(
            repository=repo_model,
            added_files=added,
            modified_files=modified,
            removed_files=removed,
            unchanged_files=unchanged,
        )

    async def list_repositories(self) -> list[RepositoryModel]:
        stmt = select(RepositoryModel).order_by(RepositoryModel.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_repository(self, repo_id: uuid.UUID) -> RepositoryModel:
        stmt = select(RepositoryModel).where(RepositoryModel.id == repo_id)
        res = await self.db.execute(stmt)
        repo = res.scalar_one_or_none()
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repositório não encontrado.",
            )
        return repo

    async def list_repository_files(self, repo_id: uuid.UUID) -> list[RepositoryFileModel]:
        await self.get_repository(repo_id)
        stmt = (
            select(RepositoryFileModel)
            .where(RepositoryFileModel.repository_id == repo_id)
            .order_by(RepositoryFileModel.relative_path.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_file_content(self, repo_id: uuid.UUID, relative_path: str) -> dict:
        repo = await self.get_repository(repo_id)
        stmt = select(RepositoryFileModel).where(
            RepositoryFileModel.repository_id == repo_id,
            RepositoryFileModel.relative_path == relative_path,
        )
        res = await self.db.execute(stmt)
        file_record = res.scalar_one_or_none()
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivo não registrado neste repositório.",
            )

        root_dir = Path(repo.local_path).resolve()
        target_file = (root_dir / relative_path).resolve()

        if not target_file.is_relative_to(root_dir) or not target_file.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Acesso negado ou caminho de arquivo inválido.",
            )

        content = target_file.read_text(encoding="utf-8", errors="replace")
        return {
            "repository_id": repo.id,
            "relative_path": file_record.relative_path,
            "language": file_record.language,
            "line_count": file_record.line_count,
            "content": content,
        }

    async def delete_repository(self, repo_id: uuid.UUID) -> None:
        repo = await self.get_repository(repo_id)
        local_dir = Path(repo.local_path).resolve()
        workspace_root = settings.REPOS_WORKSPACE_DIR.resolve()

        await self.db.delete(repo)
        await self.db.commit()

        if local_dir.exists() and local_dir.is_relative_to(workspace_root):
            shutil.rmtree(local_dir, ignore_errors=True)
