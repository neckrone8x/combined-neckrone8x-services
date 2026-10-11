from typing import List, Dict
from sentence_transformers import CrossEncoder
from app.core.config import settings

class Reranker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model = CrossEncoder(settings.rerank_model)
        return cls._instance

    def rerank(self, query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
        if not docs:
            return []
        pairs = [(query, f"{d['title']}. {d['abstract'][:2000]}") for d in docs]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: -float(x[1]))[:top_k]
        return [{**d, "rerank_score": float(s)} for d, s in ranked]
