"""
src/news/database/models.py — SQLAlchemy ORM models.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text)
    license_type: Mapped[Optional[str]] = mapped_column(Text)
    stores_full_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class NewsCategory(Base):
    __tablename__ = "news_categories"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class NewsEntity(Base):
    __tablename__ = "news_entities"
    __table_args__ = (UniqueConstraint("name", "entity_type"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text)
    ticker: Mapped[Optional[str]] = mapped_column(Text)


class NewsTopic(Base):
    __tablename__ = "news_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class NewsArticleEntity(Base):
    __tablename__ = "news_article_entities"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_entities.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Optional[str]] = mapped_column(Text)


class NewsArticleTopic(Base):
    __tablename__ = "news_article_topics"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_topics.id", ondelete="CASCADE"), primary_key=True
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_news_articles_canonical_url"),
        UniqueConstraint("content_hash", name="uq_news_articles_content_hash"),
        Index(
            "uq_news_articles_source_article_id",
            "source",
            "source_article_id",
            unique=True,
            postgresql_where=text("source_article_id IS NOT NULL")
        ),
        CheckConstraint("importance IS NULL OR (importance >= 0 AND importance <= 1)", name="chk_importance"),
        Index("idx_news_articles_published_at", "published_at", postgresql_using="btree", postgresql_ops={"published_at": "DESC"}),
        Index("idx_news_articles_source", "source"),
        Index("idx_news_articles_category", "category"),
        Index("idx_news_articles_country", "country"),
        Index("idx_news_articles_tickers", "tickers", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(ForeignKey("news_sources.id"), nullable=False)
    source_article_id: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    author: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    
    published_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    language: Mapped[Optional[str]] = mapped_column(Text)
    country: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(ForeignKey("news_categories.id"), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(Text)
    
    topics: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    entities: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    tickers: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    companies: Mapped[Optional[dict]] = mapped_column(JSONB)
    sentiment: Mapped[Optional[dict]] = mapped_column(JSONB)
    importance: Mapped[Optional[float]] = mapped_column(Numeric)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    
    duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("news_articles.id", ondelete="SET NULL"))
    raw_payload_ref: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class NewsArticleEmbedding(Base):
    __tablename__ = "news_article_embeddings"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Using Vector(384) for all-MiniLM-L6-v2 embeddings
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)



class NewsIngestionLog(Base):
    __tablename__ = "news_ingestion_logs"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'partial_failure', 'failure')", name="chk_status"),
        Index("idx_news_ingestion_logs_run_started_at", "run_started_at", postgresql_using="btree", postgresql_ops={"run_started_at": "DESC"}),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[Optional[str]] = mapped_column(ForeignKey("news_sources.id"))
    run_started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    
    articles_fetched: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    articles_inserted: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    articles_duplicate: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    articles_failed_validation: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
