import os
from typing import List, Dict
from app.core.config import settings
from app.retrieval.dense import dense_search
from app.db.session import hydrate

LOAD_RERANKER = os.getenv("NECKRONE_LOAD_LOCAL_MODELS", "true").lower() == "true"
USE_LOCAL_DB = os.getenv("NECKRONE_USE_LOCAL_DB", "true").lower() == "true"


def _rrf(rank_lists: List[List[tuple]], k: int = 60) -> List[tuple]:
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for rank, (pid, _) in enumerate(lst):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


def _hybrid_local(query: str, top_k: int) -> List[Dict]:
    """Local mode — Postgres + BM25 + reranker."""
    from app.retrieval.lexical import LexicalIndex
    dense = dense_search(query, settings.dense_top_k)
    lexical = LexicalIndex.search(query, settings.lexical_top_k)
    fused = _rrf([dense, lexical])[: settings.dense_top_k]
    ids = [pid for pid, _ in fused]
    docs_map = hydrate(ids)
    docs = [docs_map[i] for i in ids if i in docs_map]
    if not docs:
        return []
    if LOAD_RERANKER:
        from app.retrieval.reranker import Reranker
        return Reranker().rerank(query, docs, top_k=top_k)
    dense_scores = {pid: sc for pid, sc in dense}
    for d in docs:
        d["rerank_score"] = float(dense_scores.get(d["id"], 0.0))
    docs.sort(key=lambda d: -d["rerank_score"])
    return docs[:top_k]


def _hybrid_cloud(query: str, top_k: int) -> List[Dict]:
    """Cloud mode — Qdrant payloads only, no Postgres."""
    from app.embeddings.bge_embedder import get_embedder
    from app.vectorstore.qdrant_store import QdrantStore

    emb = get_embedder()
    store = QdrantStore()
    qv = emb.embed_one(query)
    hits = store.search(qv, top_k=top_k * 2)

    docs = []
    for h in hits:
        p = dict(h["payload"])
        p["id"] = p.get("paper_id", h.get("id"))
        p["rerank_score"] = float(h["score"])
        docs.append(p)

    docs.sort(key=lambda d: -d["rerank_score"])
    return docs[:top_k]


def hybrid_search(query: str, top_k: int | None = None) -> List[Dict]:
    top_k = top_k or settings.rerank_top_k
    if USE_LOCAL_DB:
        return _hybrid_local(query, top_k)
    return _hybrid_cloud(query, top_k)