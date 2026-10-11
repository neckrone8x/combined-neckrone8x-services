from typing import List, Tuple
from app.embeddings.bge_embedder import get_embedder
from app.vectorstore.qdrant_store import QdrantStore


def dense_search(query: str, top_k: int = 30) -> List[Tuple[str, float]]:
    emb = get_embedder()
    store = QdrantStore()
    v = emb.embed_one(query)
    hits = store.search(v, top_k=top_k)
    return [(h["payload"]["paper_id"], float(h["score"])) for h in hits]