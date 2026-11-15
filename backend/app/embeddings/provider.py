import hashlib
import math
from abc import ABC, abstractmethod
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

EMBEDDING_DIM = 768


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        raise NotImplementedError


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Adaptador de embeddings para o Ollama local (nomic-embed-text, 768 dims)."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.OLLAMA_EMBED_MODEL
        self.timeout = timeout

    @staticmethod
    def _deterministic_fallback_vector(text: str) -> list[float]:
        """Fallback determinístico unitário caso o servidor de inferência falhe."""
        vec: list[float] = []
        tokens = [t.lower() for t in text.replace("_", " ").replace(".", " ").split() if t]
        if not tokens:
            tokens = ["empty"]
        raw = [0.0] * EMBEDDING_DIM
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, len(digest), 2):
                idx = ((digest[i] << 8) | digest[i + 1]) % EMBEDDING_DIM
                sign = 1.0 if (digest[i] % 2 == 0) else -1.0
                raw[idx] += sign
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        vec = [round(x / norm, 6) for x in raw]
        return vec

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        sanitized = [t[:3500] if len(t) > 3500 else t for t in texts]
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model_name, "input": sanitized},
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if len(embeddings) == len(sanitized) and len(embeddings[0]) == EMBEDDING_DIM:
                    return embeddings
        except Exception as exc:
            logger.warning(
                "ollama_embed_fallback_triggered",
                model=self.model_name,
                count=len(texts),
                error=str(exc),
            )
        return [self._deterministic_fallback_vector(t) for t in sanitized]

    async def embed_query(self, query: str) -> list[float]:
        results = await self.embed_texts([query])
        return results[0]
