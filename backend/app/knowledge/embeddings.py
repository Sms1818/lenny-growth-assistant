from collections.abc import Sequence

import httpx

from app.core.config import get_settings


class OllamaEmbeddingClient:
    def __init__(self) -> None:
        settings = get_settings()

        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": list(texts),
                },
            )

            response.raise_for_status()
            payload = response.json()

        embeddings = payload.get("embeddings")

        if not isinstance(embeddings, list):
            raise ValueError("Ollama response did not contain embeddings")

        if len(embeddings) != len(texts):
            raise ValueError(
                "Ollama returned a different number of embeddings "
                f"than requested: expected {len(texts)}, got {len(embeddings)}"
            )

        for index, embedding in enumerate(embeddings):
            if len(embedding) != self.dimensions:
                raise ValueError(
                    f"Embedding {index} has {len(embedding)} dimensions; "
                    f"expected {self.dimensions}"
                )

        return embeddings
