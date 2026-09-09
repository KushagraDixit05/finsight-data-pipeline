"""
src/news/adapters/gdelt.py — Adapter for the GDELT Project DOC 2.0 API.

Provider  : GDELT Project  (https://gdeltproject.org)
Endpoint  : GET https://api.gdeltproject.org/api/v2/doc/doc
Auth      : NONE — fully public, no API key required.
Rate limit: No documented hard limit; we self-throttle with
            GDELT_INTER_QUERY_DELAY_SECONDS between keyword queries.

IMPORTANT — content storage rule (Rule 7, 02-api-selection.md)
─────────────────────────────────────────────────────────────────
  ``content`` is ALWAYS ``None`` for GDELT articles.  GDELT provides
  article METADATA (URL, title, theme tags, tone) but does NOT license the
  underlying article text — that copyright belongs to each publisher.
  Storing even a snippet of reconstructed body text would exceed GDELT's
  data-use grant.  Only title + URL + metadata are stored.

Field mapping
─────────────
  GDELT field          → NewsArticle field
  ───────────────────────────────────────────
  url                  → url
  title                → title
  seendate             → published_at  (format: YYYYMMDDTHHMMSSZ or plain YYYYMMDDHHMMSS)
  sourcecountry        → country  (GDELT 2-letter code, normalised later)
  tone                 → sentiment.raw_tone  (GDELT tone score, negative = negative tone)
  (no stable ID)       → source_article_id = None

Category assignment
───────────────────
  Each keyword query is assigned a category on construction.  The keyword list
  is designed so each bucket maps cleanly to one of our 7 categories.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

import httpx

from src.news.adapters.base import AdapterFetchError, ProviderConfig
from src.news.models.enums import NewsCategory, NewsSource
from src.news.models.news_article import NewsArticle, SentimentScore
from src.news import config as cfg

log = logging.getLogger(__name__)

# Each entry: (keyword_query, NewsCategory)
# Designed so each query maps clearly to one category; no keyword overlaps.
_QUERY_BUCKETS: list[tuple[str, NewsCategory]] = [
    ("geopolitical crisis sanctions military",   NewsCategory.GEOPOLITICAL),
    ("trade war tariff embargo",                 NewsCategory.GEOPOLITICAL),
    ("central bank interest rate monetary policy", NewsCategory.CENTRAL_BANK_MONETARY_POLICY),
    ("oil price OPEC energy supply",             NewsCategory.COMMODITIES_ENERGY),
    ("earthquake hurricane supply chain disruption", NewsCategory.COMMODITIES_ENERGY),
    ("GDP inflation employment macroeconomic",   NewsCategory.ECONOMY_MACRO),
]


def _parse_gdelt_date(raw: str) -> datetime.datetime | None:
    """
    Parse GDELT date strings.  GDELT uses two common formats:
      - 20260905T090000Z   (ISO-like with T and Z)
      - 20260905090000     (compact YYYYMMDDHHMMSS, treated as UTC)
    """
    raw = raw.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y%m%dT%H%M%S"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    log.warning("GDELT: could not parse seendate=%r", raw)
    return None


def _parse_article(raw: dict[str, Any], category: NewsCategory, fetched_at: datetime.datetime) -> NewsArticle | None:
    url = (raw.get("url") or "").strip()
    title = (raw.get("title") or "").strip()
    seendate = raw.get("seendate") or raw.get("dateadded") or ""

    if not url or not title:
        return None

    published_at = _parse_gdelt_date(seendate) if seendate else None
    if published_at is None:
        log.warning("GDELT: no valid published_at for url=%r, skipping", url[:80])
        return None

    # Tone: negative = negative sentiment (GDELT convention)
    tone: float | None = None
    try:
        tone = float(raw.get("tone", 0) or 0)
    except (TypeError, ValueError):
        pass

    country_raw = raw.get("sourcecountry") or raw.get("sourcecountry") or None
    # GDELT country codes are 2-letter ISO-like; normalizer will validate later
    country = country_raw[:2].upper() if country_raw else None

    return NewsArticle(
        source=NewsSource.GDELT,
        url=url,
        title=title,
        published_at=published_at,
        fetched_at=fetched_at,
        category=category,
        source_article_id=None,  # GDELT has no stable article ID
        description=None,
        content=None,            # RULE 7: NEVER populate content for GDELT
        image_url=None,
        language=raw.get("language", "English")[:2].lower() if raw.get("language") else None,
        country=country,
        sentiment=SentimentScore(raw_tone=tone) if tone is not None else None,
        raw_payload_ref=None,
    )


async def _fetch_one_query(
    keyword: str,
    category: NewsCategory,
    since: datetime.datetime,
    config: ProviderConfig,
    fetched_at: datetime.datetime,
) -> list[NewsArticle]:
    """Fetch one keyword query from GDELT DOC 2.0 API."""
    params = {
        "query": keyword,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 250,
        "startdatetime": since.strftime("%Y%m%d%H%M%S"),
        "enddatetime": fetched_at.strftime("%Y%m%d%H%M%S"),
        "sort": "DateDesc",
    }

    max_retries = 3
    base_url = config.base_url if config.base_url else cfg.GDELT_BASE_URL
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                response = await client.get(base_url, params=params)
                
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = (attempt + 1) * 2.0
                    log.warning("GDELT: 429 Too Many Requests for query=%r. Retrying in %ss...", keyword[:20], delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise AdapterFetchError(f"GDELT: rate limit exceeded after {max_retries} attempts for query={keyword!r}")
            
            if response.status_code != 200:
                raise AdapterFetchError(
                    f"GDELT: unexpected status {response.status_code} for query={keyword!r}"
                )
                
            break  # Success
            
        except httpx.RequestError as exc:
            raise AdapterFetchError(f"GDELT: network error for query={keyword!r}: {exc}") from exc

    # GDELT sometimes returns an empty body or HTML error page
    text = response.text.strip()
    if not text or text.startswith("<"):
        log.warning("GDELT: empty/HTML response for query=%r", keyword[:60])
        return []

    try:
        data = response.json()
    except Exception:
        log.warning("GDELT: non-JSON response for query=%r", keyword[:60])
        return []

    raw_articles: list[dict] = data.get("articles", []) or []
    results: list[NewsArticle] = []
    for raw in raw_articles:
        art = _parse_article(raw, category, fetched_at)
        if art:
            results.append(art)

    log.info("GDELT: keyword=%r → %d/%d articles mapped", keyword[:40], len(results), len(raw_articles))
    return results


async def fetch_and_map(since: datetime.datetime, config: ProviderConfig) -> list[NewsArticle]:
    """
    Query GDELT DOC 2.0 API with each keyword bucket and collect results.

    Throttles inter-query requests by GDELT_INTER_QUERY_DELAY_SECONDS to
    be a respectful API consumer.  One query failure does not abort the rest.

    No API key is required — this function will always attempt to fetch
    (unlike other adapters that check config.api_key).
    """
    fetched_at = datetime.datetime.now(datetime.timezone.utc)
    all_articles: list[NewsArticle] = []
    seen_urls: set[str] = set()  # deduplicate within this run

    for keyword, category in _QUERY_BUCKETS:
        try:
            batch = await _fetch_one_query(keyword, category, since, config, fetched_at)
            for art in batch:
                if art.url not in seen_urls:
                    seen_urls.add(art.url)
                    all_articles.append(art)
        except AdapterFetchError as exc:
            log.warning("GDELT: query failed, continuing: %s", exc)

        # Self-throttle between queries — be a good citizen
        await asyncio.sleep(cfg.GDELT_INTER_QUERY_DELAY_SECONDS)

    log.info("GDELT: total %d unique articles across %d keyword queries", len(all_articles), len(_QUERY_BUCKETS))
    return all_articles
