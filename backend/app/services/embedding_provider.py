from abc import ABC, abstractmethod
import logging
import time
from typing import Any

from openai import OpenAI

from app.services.observability import get_observability_sink

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        client: Any | None = None,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.client = client or OpenAI(api_key=api_key, base_url=base_url or None)
        self.model = model

    def embed_text(self, text: str) -> list[float]:
        started = time.monotonic()
        logger.debug("provider.embedding.start", extra={"provider": "openai", "model": self.model, "items": 1})
        generation = get_observability_sink().start_generation(
            name="embedding.embed",
            model=self.model,
            input={"count": 1, "preview": text[:240], "chars": len(text)},
            metadata={"provider": "openai", "batch_size": 1},
        )
        try:
            response = self.client.embeddings.create(model=self.model, input=text)
            embedding = list(response.data[0].embedding)
            usage = _embedding_usage([text])
            generation.finish(
                output={"count": 1, "dimensions": len(embedding), "vector_preview": embedding[:3]},
                usage=usage,
            )
            logger.debug(
                "provider.embedding.end",
                extra={"provider": "openai", "model": self.model, "items": 1, "duration_ms": int((time.monotonic() - started) * 1000)},
            )
            return embedding
        except Exception as exc:
            generation.finish(error=exc)
            logger.exception(
                "provider.embedding.failed",
                extra={"provider": "openai", "model": self.model, "items": 1, "error_type": exc.__class__.__name__},
            )
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        started = time.monotonic()
        logger.debug("provider.embedding.start", extra={"provider": "openai", "model": self.model, "items": len(texts)})
        generation = get_observability_sink().start_generation(
            name="embedding.batch_embed",
            model=self.model,
            input={"count": len(texts), "preview": [text[:160] for text in texts[:5]]},
            metadata={"provider": "openai", "batch_size": len(texts)},
        )
        try:
            response = self.client.embeddings.create(model=self.model, input=texts)
            embeddings = [list(item.embedding) for item in response.data]
            generation.finish(
                output={"count": len(embeddings), "dimensions": len(embeddings[0]) if embeddings else 0},
                usage=_embedding_usage(texts),
            )
            logger.debug(
                "provider.embedding.end",
                extra={"provider": "openai", "model": self.model, "items": len(texts), "duration_ms": int((time.monotonic() - started) * 1000)},
            )
            return embeddings
        except Exception as exc:
            generation.finish(error=exc)
            logger.exception(
                "provider.embedding.failed",
                extra={"provider": "openai", "model": self.model, "items": len(texts), "error_type": exc.__class__.__name__},
            )
            raise


def _embedding_usage(texts: list[str]) -> dict[str, Any]:
    tokens = sum((len(text) // 4) + 1 for text in texts if text)
    return {"input": tokens, "total": tokens, "unit": "TOKENS"} if tokens else {}
