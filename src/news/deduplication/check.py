"""
src/news/deduplication/check.py — Application-layer deduplication check.
"""
from __future__ import annotations

from typing import NamedTuple
from sqlalchemy.orm import Session

from src.news.models.news_article import NewsArticle as PydanticArticle
from src.news.database.models import NewsArticle as DBArticle


class DuplicateCheckResult(NamedTuple):
    is_duplicate: bool
    reason: str | None


def check_duplicate(db: Session, article: PydanticArticle) -> DuplicateCheckResult:
    """
    Check if the given normalized article is already in the database.
    Levels:
    1. canonical_url
    2. (source, source_article_id)
    3. content_hash
    """
    # Level 1: canonical_url
    if db.query(DBArticle.id).filter(DBArticle.canonical_url == article.canonical_url).first():
        return DuplicateCheckResult(True, f"Duplicate canonical_url: {article.canonical_url}")

    # Level 2: source + source_article_id
    if article.source_article_id:
        if db.query(DBArticle.id).filter(
            DBArticle.source == article.source.value,
            DBArticle.source_article_id == article.source_article_id
        ).first():
            return DuplicateCheckResult(True, f"Duplicate source_article_id: {article.source_article_id} for source: {article.source.value}")

    # Level 3: content_hash
    if db.query(DBArticle.id).filter(DBArticle.content_hash == article.content_hash).first():
        return DuplicateCheckResult(True, f"Duplicate content_hash: {article.content_hash}")

    return DuplicateCheckResult(False, None)
