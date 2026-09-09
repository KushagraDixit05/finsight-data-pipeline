"""
src/news/adapters/marketaux.py — Adapter for the Marketaux Financial News API.

Provider : Marketaux  (https://www.marketaux.com)
Endpoint : GET /v1/news/all
Auth     : API key in query parameter ``api_token``
Tier     : Free  — 100 req/day, 3 articles/request (MARKETAUX_RATE_LIMIT_PER_DAY)

Field mapping
─────────────
  Marketaux field         → NewsArticle field
  ─────────────────────────────────────────────
  uuid                    → source_article_id
  title                   → title
  description             → description
  published_at            → published_at  (ISO 8601, UTC)
  url                     → url
  source.name             → (raw origin label, stored in raw_payload_ref note)
  entities[].symbol       → tickers   (list of ticker strings)
  entities[].name         → companies (CompanyMention list)
  entities[].sentiment    → sentiment.label per entity (aggregated)
  image_url               → image_url

Content / licensing
───────────────────
  ``content`` is ALWAYS ``None``.  Storing full article text from Marketaux
  requires explicit ToS verification on content redistribution rights, which is
  an open item per 02-api-selection.md.  Only title + description are stored.

Category mapping
────────────────
  Marketaux provides a ``topics`` array (e.g. ["earnings", "mergers_acquisitions"]).
  We map the first recognisable topic to our 7-category taxonomy; unrecognised →
  NewsCategory.MARKETS (safe fallback for financial news).
"""

from __future__ import annotations

import datetime
import hashlib
import logging
from typing import Any

import httpx

from src.news.adapters.base import (
    AdapterAuthError,
    AdapterFetchError,
    AdapterRateLimitError,
    ProviderConfig,
    sanitize_error_msg,
)
from src.news.models.enums import NewsCategory, NewsSource
from src.news.models.news_article import CompanyMention, NewsArticle, SentimentScore

log = logging.getLogger(__name__)

_BASE_URL = "https://api.marketaux.com/v1/news/all"

# Marketaux topic → our NewsCategory
_TOPIC_MAP: dict[str, NewsCategory] = {
    "earnings":               NewsCategory.COMPANY,
    "mergers_acquisitions":   NewsCategory.COMPANY,
    "ipo":                    NewsCategory.COMPANY,
    "dividends":              NewsCategory.COMPANY,
    "buybacks":               NewsCategory.COMPANY,
    "insider_trading":        NewsCategory.COMPANY,
    "corporate_governance":   NewsCategory.COMPANY,
    "analyst_ratings":        NewsCategory.COMPANY,
    "product_launches":       NewsCategory.COMPANY,
    "central_banks":          NewsCategory.CENTRAL_BANK_MONETARY_POLICY,
    "federal_reserve":        NewsCategory.CENTRAL_BANK_MONETARY_POLICY,
    "interest_rates":         NewsCategory.CENTRAL_BANK_MONETARY_POLICY,
    "inflation":              NewsCategory.ECONOMY_MACRO,
    "gdp":                    NewsCategory.ECONOMY_MACRO,
    "employment":             NewsCategory.ECONOMY_MACRO,
    "trade":                  NewsCategory.ECONOMY_MACRO,
    "regulation":             NewsCategory.GOVERNMENT_REGULATION,
    "legal":                  NewsCategory.GOVERNMENT_REGULATION,
    "sanctions":              NewsCategory.GEOPOLITICAL,
    "geopolitics":            NewsCategory.GEOPOLITICAL,
    "oil":                    NewsCategory.COMMODITIES_ENERGY,
    "commodities":            NewsCategory.COMMODITIES_ENERGY,
    "energy":                 NewsCategory.COMMODITIES_ENERGY,
}


def _map_category(topics: list[str] | None) -> NewsCategory:
    if not topics:
        return NewsCategory.MARKETS
    for topic in topics:
        cat = _TOPIC_MAP.get(topic.lower())
        if cat:
            return cat
    return NewsCategory.MARKETS


def _map_sentiment(entities: list[dict[str, Any]]) -> SentimentScore | None:
    """Aggregate sentiment labels from entity list into a single SentimentScore."""
    labels = [e.get("sentiment_score") for e in entities if e.get("sentiment_score") is not None]
    if not labels:
        return None
    avg = sum(labels) / len(labels)
    if avg > 0.1:
        label = "Bullish"
    elif avg < -0.1:
        label = "Bearish"
    else:
        label = "Neutral"
    return SentimentScore(label=label, score=round(avg, 4))


def _parse_article(raw: dict[str, Any], fetched_at: datetime.datetime) -> NewsArticle | None:
    """Map a single Marketaux article dict to NewsArticle. Returns None on missing required fields."""
    url = raw.get("url", "").strip()
    title = raw.get("title", "").strip()
    published_str = raw.get("published_at", "")
    if not url or not title or not published_str:
        log.warning("Marketaux: skipping article missing url/title/published_at")
        return None

    try:
        published_at = datetime.datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=datetime.timezone.utc)
        else:
            published_at = published_at.astimezone(datetime.timezone.utc)
    except (ValueError, AttributeError):
        log.warning("Marketaux: could not parse published_at=%r, skipping", published_str)
        return None

    entities: list[dict[str, Any]] = raw.get("entities", []) or []
    tickers = [e["symbol"] for e in entities if e.get("symbol")]
    companies = [
        CompanyMention(name=e["name"], ticker=e.get("symbol"))
        for e in entities if e.get("name")
    ]
    topics: list[str] = raw.get("topics", []) or []
    topic_names = [t.get("topic", t) if isinstance(t, dict) else t for t in topics]

    return NewsArticle(
        source=NewsSource.MARKETAUX,
        url=url,
        title=title,
        published_at=published_at,
        fetched_at=fetched_at,
        category=_map_category(topic_names),
        source_article_id=raw.get("uuid"),
        description=raw.get("description") or None,
        content=None,  # ToS verification pending — never store
        image_url=raw.get("image_url") or None,
        language=raw.get("language") or None,
        tickers=tickers or None,
        companies=companies or None,
        sentiment=_map_sentiment(entities),
        topics=topic_names or None,
        raw_payload_ref=None,
    )


async def fetch_and_map(since: datetime.datetime, config: ProviderConfig) -> list[NewsArticle]:
    """
    Fetch articles from Marketaux published after ``since`` and map to NewsArticle.

    Raises:
        AdapterAuthError       — HTTP 401 / 403 (bad or expired API key).
        AdapterRateLimitError  — HTTP 429 (daily request quota reached).
        AdapterFetchError      — Any other error (network, unexpected status).
    """
    if not config.api_key:
        log.warning("Marketaux: MARKETAUX_API_KEY not configured, skipping provider")
        return []

    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    params = {
        "api_token": config.api_key,
        "published_after": since.strftime("%Y-%m-%dT%H:%M"),
        "language": "en",
        "limit": min(config.max_articles_per_request, 3),  # free tier: 3/request
    }

    base_url = config.base_url if config.base_url else _BASE_URL
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.get(base_url, params=params)
    except httpx.RequestError as exc:
        err_msg = sanitize_error_msg(str(exc), config)
        raise AdapterFetchError(f"Marketaux: network error: {err_msg}") from exc

    if response.status_code in (401, 403):
        raise AdapterAuthError(f"Marketaux: auth error {response.status_code}")
    if response.status_code == 429:
        raise AdapterRateLimitError("Marketaux: rate limit exceeded (100 req/day)")
    if response.status_code != 200:
        err_msg = sanitize_error_msg(response.text[:200], config)
        raise AdapterFetchError(f"Marketaux: unexpected status {response.status_code}: {err_msg}")

    try:
        data = response.json()
    except Exception as exc:
        raise AdapterFetchError(f"Marketaux: invalid JSON response: {exc}") from exc

    raw_articles: list[dict] = data.get("data", []) or []
    articles: list[NewsArticle] = []
    for raw in raw_articles:
        article = _parse_article(raw, fetched_at)
        if article:
            articles.append(article)

    log.info("Marketaux: fetched %d articles (%d mapped)", len(raw_articles), len(articles))
    return articles
