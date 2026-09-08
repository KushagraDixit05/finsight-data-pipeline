import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.news.models.news_article import NewsArticle
from src.news.models.enums import NewsSource, NewsCategory
from src.news.deduplication.check import check_duplicate, DuplicateCheckResult
from src.news.database.repository import get_last_successful_run
from src.news.scheduler.window import compute_fetch_window
from src.news.database.models import NewsArticle as DBArticle

def get_base_article(url="https://example.com"):
    return NewsArticle(
        source=NewsSource.MARKETAUX,
        url=url,
        canonical_url=url.replace("https://", ""),
        title="Test Title",
        published_at=datetime.now(timezone.utc),
        fetched_at=datetime.now(timezone.utc),
        category=NewsCategory.MARKETS,
        content_hash="hash-" + url,
        source_article_id=url.split("/")[-1]
    )

def test_deduplication_mock():
    mock_db = MagicMock()
    
    # 1. Exact canonical URL duplicate
    article1 = get_base_article("https://example.com/1")
    mock_db.query().filter().first.return_value = True # Simulate match found
    
    dup_res = check_duplicate(mock_db, article1)
    assert dup_res.is_duplicate is True
    assert "canonical_url" in dup_res.reason
    
    # 2. Source + source_article_id duplicate
    mock_db.query().filter().first.side_effect = [None, True] # First level miss, second level hit
    dup_res = check_duplicate(mock_db, article1)
    assert dup_res.is_duplicate is True
    assert "source_article_id" in dup_res.reason
    
    # 3. Content hash duplicate
    mock_db.query().filter().first.side_effect = [None, None, True] # Level 1, 2 miss, Level 3 hit
    dup_res = check_duplicate(mock_db, article1)
    assert dup_res.is_duplicate is True
    assert "content_hash" in dup_res.reason

    # Not duplicate
    mock_db.query().filter().first.side_effect = [None, None, None]
    dup_res = check_duplicate(mock_db, article1)
    assert dup_res.is_duplicate is False

def test_window_computation_mock(monkeypatch):
    mock_db = MagicMock()
    
    # First run (no successful run)
    monkeypatch.setattr("src.news.scheduler.window.get_last_successful_run", lambda db, src: None)
    window = compute_fetch_window(mock_db)
    now = datetime.now(timezone.utc)
    assert (now - window).days == 30
    
    # Subsequent run
    run_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("src.news.scheduler.window.get_last_successful_run", lambda db, src: run_time)
    window2 = compute_fetch_window(mock_db)
    assert window2.year == 2025
    assert window2.hour == 11
    assert window2.minute == 30

