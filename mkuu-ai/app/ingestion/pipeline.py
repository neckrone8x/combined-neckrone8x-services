from typing import List
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.db.session import init_db, get_session
from app.db.models import Paper
from app.embeddings.bge_embedder import get_embedder
from app.vectorstore.qdrant_store import QdrantStore, to_uuid
from app.sources.arxiv_source import ArxivSource
from app.sources.openalex_source import OpenAlexSource

SOURCES = {
    "arxiv": ArxivSource(),
    "openalex": OpenAlexSource(),
}

def run_ingestion(queries: List[str], sources: List[str] | None = None,
                  per_query: int = 50, verbose: bool = True) -> int:
    sources = sources or ["arxiv"]
    init_db()
    embedder = get_embedder()
    store = QdrantStore()
    session = get_session()

    seen: set[str] = set()

    for src_name in sources:
        src = SOURCES[src_name]
        for q in queries:
            if verbose:
                print(f"[{src_name}] query: {q}")
            try:
                papers = src.fetch(q, per_query)
            except Exception as e:
                print(f"  ! source error: {e}")
                continue

            new = [p for p in papers if p["id"] not in seen]
            if not new:
                continue
            seen.update(p["id"] for p in new)

            texts = [f"{p['title']}. {p['abstract']}" for p in new]
            vecs = embedder.embed(texts)

            rows = [{k: p.get(k) for k in (
                "id", "source", "source_id", "doi", "title", "abstract",
                "authors", "categories", "fields", "published", "url", "extra"
            )} for p in new]
            for row in rows:
                stmt = (pg_insert(Paper).values(**row)
                        .on_conflict_do_nothing(index_elements=["id"]))
                session.execute(stmt)
            session.commit()

            ids = [to_uuid(p["id"]) for p in new]
            payloads = [{
                "paper_id": p["id"],
                "title": p["title"],
                "abstract": p["abstract"],
                "authors": p.get("authors", []),
                "source": p["source"],
                "url": p.get("url"),
                "published": p.get("published"),
                "fields": p.get("fields", []),
                "categories": p.get("categories", []),
                "doi": p.get("doi"),
            } for p in new]
            store.upsert(ids, vecs, payloads)

            if verbose:
                print(f"  + {len(new)} papers indexed")

    session.close()

    try:
        from app.retrieval.lexical import LexicalIndex
        LexicalIndex.invalidate()
    except Exception:
        pass

    return len(seen)
