import uuid
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.schemas import (
    FileContentResponse,
    GitImportRequest,
    RepositoryFileResponse,
    RepositoryResponse,
    SyncResultResponse,
)
from app.infrastructure.database.session import get_db_session
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["Repository Manager"])


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    db: AsyncSession = Depends(get_db_session),
) -> list[RepositoryResponse]:
    service = RepositoryService(db)
    return await service.list_repositories()


@router.post("/git", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def import_git_repository(
    payload: GitImportRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    service = RepositoryService(db)
    return await service.import_git_repository(payload)


@router.post("/upload", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def import_zip_repository(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    service = RepositoryService(db)
    return await service.import_zip_repository(file=file, name=name)


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    service = RepositoryService(db)
    return await service.get_repository(repo_id)


@router.get("/{repo_id}/files", response_model=list[RepositoryFileResponse])
async def list_repository_files(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[RepositoryFileResponse]:
    service = RepositoryService(db)
    return await service.list_repository_files(repo_id)


@router.get("/{repo_id}/files/content", response_model=FileContentResponse)
async def get_repository_file_content(
    repo_id: uuid.UUID,
    path: str = Query(..., description="Caminho relativo do arquivo dentro do repositório"),
    db: AsyncSession = Depends(get_db_session),
) -> FileContentResponse:
    service = RepositoryService(db)
    return await service.get_file_content(repo_id, path)


@router.post("/{repo_id}/sync", response_model=SyncResultResponse)
async def sync_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> SyncResultResponse:
    service = RepositoryService(db)
    return await service.sync_repository(repo_id)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = RepositoryService(db)
    await service.delete_repository(repo_id)
