"""
src/news/database/repository.py — Data access layer.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from src.news.models.news_article import NewsArticle as PydanticArticle
from src.news.database.models import NewsArticle, NewsIngestionLog

log = logging.getLogger(__name__)

def insert_article(db: Session, article: PydanticArticle) -> bool:
    """
    Insert a single normalized and validated article.
    Catches IntegrityError to skip duplicates.
    Returns True if inserted, False if skipped.
    """
    # exclude_none=True prevents SQLAlchemy from explicitly setting columns 
    # to NULL when they have a server_default (like id, created_at, updated_at).
    data = article.model_dump(exclude_none=True)
    
    if article.source:
        data["source"] = article.source.value
    if article.category:
        data["category"] = article.category.value
        
    db_article = NewsArticle(**data)
    db.add(db_article)
    try:
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        log.info("Duplicate article skipped at database level: %s", article.canonical_url)
        return False
    except Exception as e:
        db.rollback()
        log.error("Failed to insert article: %s", str(e))
        raise

def get_last_successful_run(db: Session, source: Optional[str] = None) -> Optional[datetime]:
    """
    Get the run_started_at timestamp of the last successful ingestion run.
    """
    query = db.query(NewsIngestionLog.run_started_at).filter(NewsIngestionLog.status == "success")
    if source:
        query = query.filter(NewsIngestionLog.source == source)
    else:
        query = query.filter(NewsIngestionLog.source.is_(None))
        
    result = query.order_by(NewsIngestionLog.run_started_at.desc()).first()
    return result[0] if result else None

def log_ingestion_run(
    db: Session,
    source: Optional[str],
    run_started_at: datetime,
    run_finished_at: datetime,
    status: str,
    articles_fetched: int = 0,
    articles_inserted: int = 0,
    articles_duplicate: int = 0,
    articles_failed_validation: int = 0,
    error_summary: Optional[str] = None
) -> str:
    """
    Record the results of an ingestion run.
    """
    log_entry = NewsIngestionLog(
        source=source,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        status=status,
        articles_fetched=articles_fetched,
        articles_inserted=articles_inserted,
        articles_duplicate=articles_duplicate,
        articles_failed_validation=articles_failed_validation,
        error_summary=error_summary
    )
    db.add(log_entry)
    db.commit()
    return str(log_entry.id)
