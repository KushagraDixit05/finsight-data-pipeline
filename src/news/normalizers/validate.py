"""
src/news/normalizers/validate.py — Article validation rules.
"""

from __future__ import annotations

import datetime
from typing import NamedTuple

from src.news.models.news_article import NewsArticle
from src.news.normalizers.datetime_utils import UTC


class ValidationResult(NamedTuple):
    ok: bool
    reason: str | None


def validate(article: NewsArticle, max_age_days: int = 30) -> ValidationResult:
    """
    Apply validation rules to a normalized NewsArticle.
    Returns ValidationResult(ok=True, reason=None) if valid,
    or ValidationResult(ok=False, reason="...") if rejected.
    """
    # Check required fields
    if not article.source:
        return ValidationResult(False, "Missing required field: source")
    if not article.url:
        return ValidationResult(False, "Missing required field: url")
    if not article.title or not article.title.strip():
        return ValidationResult(False, "Missing or empty required field: title")
    if not article.published_at:
        return ValidationResult(False, "Missing required field: published_at")
    if not article.fetched_at:
        return ValidationResult(False, "Missing required field: fetched_at")
    if not article.category:
        return ValidationResult(False, "Missing required field: category")

    # The normalizer sets canonical_url only if the URL is valid
    if not article.canonical_url:
        return ValidationResult(False, f"url does not parse as a valid absolute URL: {article.url}")

    now = datetime.datetime.now(UTC)
    
    # Future check: more than 24 hours in the future
    if article.published_at > now + datetime.timedelta(hours=24):
        return ValidationResult(False, f"published_at is too far in the future: {article.published_at}")

    # Historical floor check
    if article.published_at < now - datetime.timedelta(days=max_age_days):
        return ValidationResult(False, f"published_at is older than {max_age_days} days: {article.published_at}")

    return ValidationResult(True, None)
