import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.database.session import get_db_session

router = APIRouter(tags=["Health & Diagnostics"])


class ComponentStatus(BaseModel):
    status: str
    details: dict = {}


class SystemHealthResponse(BaseModel):
    app_name: str
    version: str
    overall_status: str
    database: ComponentStatus
    redis: ComponentStatus
    ollama: ComponentStatus


@router.get("/health", response_model=SystemHealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> SystemHealthResponse:
    # 1. Verificar PostgreSQL + pgvector
    try:
        ext_res = await db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        )
        pgvector_version = ext_res.scalar_one_or_none()
        count_res = await db.execute(text("SELECT COUNT(*) FROM repositories;"))
        repo_count = count_res.scalar_one() or 0

        db_status = ComponentStatus(
            status="healthy" if pgvector_version else "degraded",
            details={
                "connected": True,
                "pgvector_installed": bool(pgvector_version),
                "pgvector_version": pgvector_version,
                "repositories_registered": repo_count,
            },
        )
    except Exception as exc:
        db_status = ComponentStatus(
            status="unhealthy",
            details={"connected": False, "error": str(exc)},
        )

    # 2. Verificar Redis
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await redis_client.ping()
        await redis_client.aclose()
        redis_status = ComponentStatus(
            status="healthy" if pong else "unhealthy",
            details={"connected": bool(pong)},
        )
    except Exception as exc:
        redis_status = ComponentStatus(
            status="unhealthy",
            details={"connected": False, "error": str(exc)},
        )

    # 3. Verificar Ollama Local e modelos configurados
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            installed_models = [m.get("name", "") for m in data.get("models", [])]

            has_llm = any(
                settings.OLLAMA_LLM_MODEL in m for m in installed_models
            )
            has_embed = any(
                settings.OLLAMA_EMBED_MODEL in m for m in installed_models
            )

            ollama_status = ComponentStatus(
                status="healthy" if (has_llm and has_embed) else "degraded",
                details={
                    "connected": True,
                    "configured_llm": settings.OLLAMA_LLM_MODEL,
                    "llm_ready": has_llm,
                    "configured_embedding": settings.OLLAMA_EMBED_MODEL,
                    "embedding_ready": has_embed,
                    "available_models": installed_models,
                },
            )
    except Exception as exc:
        ollama_status = ComponentStatus(
            status="unhealthy",
            details={
                "connected": False,
                "base_url": settings.OLLAMA_BASE_URL,
                "error": str(exc),
            },
        )

    all_statuses = [db_status.status, redis_status.status, ollama_status.status]
    if all(s == "healthy" for s in all_statuses):
        overall = "healthy"
    elif "unhealthy" in all_statuses:
        overall = "unhealthy"
    else:
        overall = "degraded"

    return SystemHealthResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        overall_status=overall,
        database=db_status,
        redis=redis_status,
        ollama=ollama_status,
    )