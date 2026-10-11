import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import Base, Paper

USE_LOCAL_DB = os.getenv("NECKRONE_USE_LOCAL_DB", "true").lower() == "true"

if USE_LOCAL_DB:
    engine = create_engine(settings.pg_dsn, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
else:
    engine = None
    SessionLocal = None

def init_db():
    if engine is not None:
        Base.metadata.create_all(engine)

def get_session():
    if SessionLocal is None:
        return None
    return SessionLocal()

def all_papers_brief():
    if SessionLocal is None:
        return []
    with get_session() as s:
        return s.execute(select(Paper.id, Paper.title, Paper.abstract)).all()

def hydrate(ids: list[str]) -> dict[str, dict]:
    if SessionLocal is None:
        return {}
    with get_session() as s:
        rows = s.execute(select(Paper).where(Paper.id.in_(ids))).scalars().all()
    return {
        r.id: {
            "id": r.id, "title": r.title, "abstract": r.abstract,
            "authors": r.authors or [], "url": r.url, "source": r.source,
            "fields": r.fields or [], "doi": r.doi,
            "published": r.published.isoformat() if r.published else None,
            "categories": r.categories or [],
        }
        for r in rows
    }