"""
src/news/scheduler/window.py — Compute the overlap window for fetching news.
"""
import datetime
from typing import Optional
from sqlalchemy.orm import Session
from src.news.database.repository import get_last_successful_run
from src.news.normalizers.datetime_utils import UTC

OVERLAP_WINDOW_MINUTES = 30
MAX_ARTICLE_AGE_DAYS = 30

def compute_fetch_window(db: Session, source: Optional[str] = None) -> datetime.datetime:
    """
    Determine the 'since' datetime for fetching news to overlap the last run.
    """
    last_run = get_last_successful_run(db, source)
    now = datetime.datetime.now(UTC)
    
    if last_run:
        return last_run - datetime.timedelta(minutes=OVERLAP_WINDOW_MINUTES)
    else:
        return now - datetime.timedelta(days=MAX_ARTICLE_AGE_DAYS)
