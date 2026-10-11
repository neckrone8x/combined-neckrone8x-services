import os
import httpx
from typing import List


class CloudEmbedder:
    """Jina AI embeddings (free tier). 1024-dim, matches BGE-M3."""

    def __init__(self):
        self.api_key = os.getenv("JINA_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("JINA_API_KEY not set")
        self.url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"

    def embed(self, texts: List[str]) -> List[List[float]]:
        with httpx.Client(timeout=60) as c:
            r = c.post(self.url,
                       headers={"Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"},
                       json={"input": texts, "model": self.model,
                             "dimensions": 1024})
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]