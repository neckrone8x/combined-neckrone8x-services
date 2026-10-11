import os
from typing import List
from app.core.config import settings


def get_embedder():
    """Pick an embedder based on which API key is set (in order of preference)."""
    if os.getenv("GEMINI_API_KEY"):
        from app.embeddings.gemini_embedder import GeminiEmbedder
        return GeminiEmbedder()
    if os.getenv("COHERE_API_KEY"):
        from app.embeddings.cohere_embedder import CohereEmbedder
        return CohereEmbedder()
    if os.getenv("JINA_API_KEY"):
        from app.embeddings.cloud_embedder import CloudEmbedder
        return CloudEmbedder()
    return Embedder()


class Embedder:
    """Local BGE-M3 embedder — only used when no cloud key is set."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            from sentence_transformers import SentenceTransformer
            cls._instance.model = SentenceTransformer(settings.embed_model)
        return cls._instance

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(
            texts, normalize_embeddings=True,
            batch_size=32, show_progress_bar=False,
        ).tolist()

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]