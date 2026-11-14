import uuid
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ConfidenceLevel, RelationType, SymbolType
from app.domain.schemas import (
    AnalysisSummaryResponse,
    CodeSymbolResponse,
    FileContentResponse,
    GitImportRequest,
    RepositoryFileResponse,
    RepositoryResponse,
    SymbolRelationshipResponse,
    SyncResultResponse,
)
from app.infrastructure.database.session import get_db_session
from app.services.analysis_service import CodeAnalysisService
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["Repository & AST Analysis"])


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    db: AsyncSession = Depends(get_db_session),
) -> list[RepositoryResponse]:
    return await RepositoryService(db).list_repositories()


@router.post("/git", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def import_git_repository(
    payload: GitImportRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    return await RepositoryService(db).import_git_repository(payload)


@router.post("/upload", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def import_zip_repository(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    return await RepositoryService(db).import_zip_repository(file=file, name=name)


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RepositoryResponse:
    return await RepositoryService(db).get_repository(repo_id)


@router.get("/{repo_id}/files", response_model=list[RepositoryFileResponse])
async def list_repository_files(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[RepositoryFileResponse]:
    return await RepositoryService(db).list_repository_files(repo_id)


@router.get("/{repo_id}/files/content", response_model=FileContentResponse)
async def get_repository_file_content(
    repo_id: uuid.UUID,
    path: str = Query(..., description="Caminho relativo do arquivo dentro do repositório"),
    db: AsyncSession = Depends(get_db_session),
) -> FileContentResponse:
    return await RepositoryService(db).get_file_content(repo_id, path)


@router.post("/{repo_id}/sync", response_model=SyncResultResponse)
async def sync_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> SyncResultResponse:
    return await RepositoryService(db).sync_repository(repo_id)


@router.post("/{repo_id}/analyze", response_model=AnalysisSummaryResponse)
async def analyze_repository_ast(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> AnalysisSummaryResponse:
    return await CodeAnalysisService(db).analyze_repository(repo_id)


@router.get("/{repo_id}/symbols", response_model=list[CodeSymbolResponse])
async def list_repository_symbols(
    repo_id: uuid.UUID,
    symbol_type: SymbolType | None = Query(default=None),
    file_path: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[CodeSymbolResponse]:
    return await CodeAnalysisService(db).list_symbols(
        repo_id=repo_id,
        symbol_type=symbol_type,
        file_path=file_path,
        search=search,
    )


@router.get("/{repo_id}/relationships", response_model=list[SymbolRelationshipResponse])
async def list_repository_relationships(
    repo_id: uuid.UUID,
    relation_type: RelationType | None = Query(default=None),
    confidence: ConfidenceLevel | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[SymbolRelationshipResponse]:
    return await CodeAnalysisService(db).list_relationships(
        repo_id=repo_id,
        relation_type=relation_type,
        confidence=confidence,
    )


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await RepositoryService(db).delete_repository(repo_id)
