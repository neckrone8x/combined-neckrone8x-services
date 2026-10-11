import re
from typing import List, Tuple
from rank_bm25 import BM25Okapi
from app.db.session import all_papers_brief

_TOKEN = re.compile(r"[a-zA-Z0-9]+")

class LexicalIndex:
    _bm25: BM25Okapi | None = None
    _ids: List[str] | None = None

    @classmethod
    def invalidate(cls):
        cls._bm25 = None
        cls._ids = None

    @classmethod
    def load(cls):
        rows = all_papers_brief()
        cls._ids = [r[0] for r in rows]
        corpus = [_TOKEN.findall(f"{r[1]} {r[2]}".lower()) for r in rows]
        cls._bm25 = BM25Okapi(corpus) if corpus else None
        return cls._bm25

    @classmethod
    def search(cls, query: str, top_k: int = 30) -> List[Tuple[str, float]]:
        if cls._bm25 is None:
            cls.load()
        if cls._bm25 is None:
            return []
        tokens = _TOKEN.findall(query.lower())
        scores = cls._bm25.get_scores(tokens)
        order = scores.argsort()[::-1][:top_k]
        return [(cls._ids[i], float(scores[i])) for i in order if scores[i] > 0]
