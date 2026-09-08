import pytest
from datetime import datetime, timezone
from src.news.models.news_article import NewsArticle
from src.news.models.enums import NewsSource, NewsCategory
from src.news.normalizers.pipeline import normalize
from src.news.normalizers.validate import validate

def get_base_article() -> dict:
    return {
        "source": NewsSource.MARKETAUX,
        "url": "https://example.com/news?utm_source=test",
        "title": "  Hello <b>World</b>  ",
        "published_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "fetched_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
        "category": NewsCategory.MARKETS,
        "country": "us",
        "language": "en-US",
        "author": " Staff "
    }

def test_pipeline_normalization():
    article = NewsArticle(**get_base_article())
    normalized = normalize(article)
    
    assert normalized.title == "Hello World"
    assert normalized.canonical_url == "example.com/news"
    assert normalized.country == "US"
    assert normalized.language == "en"
    assert normalized.author is None
    assert normalized.content_hash is not None

def test_validate_success():
    article = NewsArticle(**get_base_article())
    normalized = normalize(article)
    # Using a max_age of large enough to not fail the 30 day limit if test runs in 2026
    val_result = validate(normalized, max_age_days=10000)
    assert val_result.ok is True

def test_validate_missing_title():
    data = get_base_article()
    data["title"] = "   "
    article = NewsArticle(**data)
    normalized = normalize(article)
    val_result = validate(normalized, max_age_days=10000)
    assert val_result.ok is False
    assert "title" in val_result.reason
