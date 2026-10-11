import os
import time
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core.config import settings


def to_uuid(paper_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, paper_id))


class QdrantStore:
    def __init__(self, collection: str = None, dim: int = None):
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        if api_key:
            api_key = api_key.strip()
        if url and api_key:
            print(f"[qdrant] cloud mode: {url}")
            self.client = QdrantClient(
                url=url, api_key=api_key,
                timeout=60.0,  # seconds per request
            )
        else:
            print("[qdrant] local mode")
            self.client = QdrantClient(
                host=settings.qdrant_host, port=settings.qdrant_port)
        self.collection = collection or settings.qdrant_collection
        self.dim = dim or settings.embed_dim
        self._ensure()

    def _ensure(self):
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE))

    def upsert(self, ids, vectors, payloads, batch_size: int = 20):
        """Upload in small batches with retry."""
        n = len(ids)
        for i in range(0, n, batch_size):
            chunk_ids = ids[i:i+batch_size]
            chunk_vecs = vectors[i:i+batch_size]
            chunk_pls = payloads[i:i+batch_size]
            points = [PointStruct(id=chunk_ids[j], vector=chunk_vecs[j],
                                  payload=chunk_pls[j])
                      for j in range(len(chunk_ids))]
            for attempt in range(4):
                try:
                    self.client.upsert(collection_name=self.collection,
                                       points=points)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    wait = 2 ** attempt
                    print(f"  [qdrant] upsert failed ({e.__class__.__name__}), "
                          f"retry in {wait}s")
                    time.sleep(wait)
            if i + batch_size < n:
                time.sleep(0.5)  # small pause between batches

    def search(self, vector, top_k: int = 10):
        res = self.client.query_points(
            collection_name=self.collection, query=vector, limit=top_k)
        return [{"id": p.id, "score": p.score, "payload": p.payload}
                for p in res.points]