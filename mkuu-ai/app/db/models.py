from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    published: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

Index("ix_papers_source_id", Paper.source, Paper.source_id)
