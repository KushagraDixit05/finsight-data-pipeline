"""
src/news/adapters/newsdata.py — Adapter for the NewsData.io News API.

Provider: NewsData.io  (https://newsdata.io/documentation)
Endpoint: GET /api/1/news
Auth    : API key in query parameter ``apikey``
Tier    : Free — 200 credits/day (NEWSDATA_RATE_LIMIT_PER_DAY)
          Each successful response costs 1 credit.

Fetch strategy
──────────────
Two sequential calls are made per scheduler run:
  1. country=in  — India-specific financial/business news
  2. (no country) — Global business/finance news

This dual-call strategy ensures India-focused coverage without losing global
macro signals.  Both result sets are combined and deduplicated by
``source_article_id`` before being returned.

Field mapping
─────────────
  NewsData field    → NewsArticle field
  ──────────────────────────────────────
  article_id        → source_article_id
  title             → title
  description       → description
  pubDate           → published_at  (parsed defensively, assumed UTC)
  source_id         → stored; NewsSource.NEWSDATA always set
  country[0]        → country  (first element, upper-cased to ISO 3166-1 α-2)
  link              → url
  image_url         → image_url
  language          → language
  category[0]       → category  (via CATEGORY_MAP below)
  keywords          → topics

Category mapping
────────────────
  NewsData category → NewsCategory
  ─────────────────────────────────
  business          → MARKETS
  politics          → GOVERNMENT_REGULATION
  world             → GEOPOLITICAL
  science           → ECONOMY_MACRO
  technology        → COMPANY
  <anything else>   → MARKETS  (fallback)

Content / licensing
───────────────────
  ``content`` is always ``None``.  NewsData.io supplies a ``content`` field on
  paid plans only.  Even on paid plans, re-storage may require additional
  licensing.  Set to None until verified (02-api-selection.md §Content storage).

Date parsing
────────────
  NewsData returns dates as strings in the format "YYYY-MM-DD HH:MM:SS".
  The API documents these as UTC but doesn't always attach a timezone.
  We parse defensively and attach UTC explicitly.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.news.adapters.base import (
    AdapterAuthError,
    AdapterFetchError,
    AdapterRateLimitError,
    ProviderConfig,
)
from src.news.models import NewsArticle, NewsCategory, NewsSource

logger = logging.getLogger(__name__)

_ENDPOINT_PATH = "/api/1/news"

# NewsData category → canonical NewsCategory
# All categories from https://newsdata.io/documentation/#news-sources-category
CATEGORY_MAP: dict[str, NewsCategory] = {
    "business":    NewsCategory.MARKETS,
    "politics":    NewsCategory.GOVERNMENT_REGULATION,
    "world":       NewsCategory.GEOPOLITICAL,
    "science":     NewsCategory.ECONOMY_MACRO,
    "technology":  NewsCategory.COMPANY,
    "sports":      NewsCategory.MARKETS,       # fallback — unlikely in finance
    "health":      NewsCategory.MARKETS,       # fallback
    "entertainment": NewsCategory.MARKETS,     # fallback
    "environment": NewsCategory.COMMODITIES_ENERGY,
    "food":        NewsCategory.COMMODITIES_ENERGY,
    "tourism":     NewsCategory.MARKETS,
    "top":         NewsCategory.MARKETS,
    "other":       NewsCategory.MARKETS,
}

_FALLBACK_CATEGORY = NewsCategory.MARKETS


def _parse_pubdate(pubdate_str: str | None) -> datetime:
    """
    Parse NewsData.io's pubDate string to a UTC-aware datetime.

    NewsData returns dates as "YYYY-MM-DD HH:MM:SS" (documented UTC).
    Falls back to now(UTC) if the string is missing or unparseable.
    """
    if not pubdate_str:
        logger.warning("NewsData article has no pubDate, using now(UTC)")
        return datetime.now(UTC)

    # Attempt ISO-format parse first (handles "YYYY-MM-DD HH:MM:SS")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            naive = datetime.strptime(pubdate_str, fmt)
            return naive.replace(tzinfo=UTC)
        except ValueError:
            continue

    # Last resort: fromisoformat (Python 3.11+ handles most ISO variants)
    try:
        dt = datetime.fromisoformat(pubdate_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        logger.warning("Cannot parse NewsData pubDate %r, using now(UTC)", pubdate_str)
        return datetime.now(UTC)


def _map_category(categories: list[str] | None) -> NewsCategory:
    """Map the first element of NewsData's categories list to a canonical category."""
    if not categories:
        return _FALLBACK_CATEGORY
    first = categories[0].lower().strip() if categories else ""
    return CATEGORY_MAP.get(first, _FALLBACK_CATEGORY)


def _map_article(raw: dict[str, Any]) -> NewsArticle | None:
    """
    Map a single NewsData.io JSON article to a canonical NewsArticle.

    Returns ``None`` if essential fields (link, title) are missing so callers
    can skip malformed records without crashing.
    """
    url: str = (raw.get("link") or "").strip()
    title: str = (raw.get("title") or "").strip()

    if not url or not title:
        logger.debug("Skipping NewsData record — missing url or title: %s", raw.get("article_id"))
        return None

    # country: take first element and uppercase to ISO 3166-1 α-2
    countries: list[str] = raw.get("country") or []
    country: str | None = countries[0].upper() if countries else None

    # keywords from NewsData
    keywords: list[str] | None = raw.get("keywords") or None

    return NewsArticle(
        source=NewsSource.NEWSDATA,
        url=url,
        title=title,
        description=raw.get("description") or None,
        content=None,  # ToS / licensing constraint — never stored
        image_url=raw.get("image_url") or None,
        published_at=_parse_pubdate(raw.get("pubDate")),
        fetched_at=datetime.now(UTC),
        category=_map_category(raw.get("category")),
        source_article_id=raw.get("article_id") or None,
        language=raw.get("language") or None,
        country=country,
        topics=keywords if keywords else None,
    )


async def _fetch_page(
    client: httpx.AsyncClient,
    base_url: str,
    params: dict[str, Any],
    config: ProviderConfig,
) -> list[dict[str, Any]]:
    """
    Execute one GET /api/1/news request and return the ``results`` list.

    Raises adapter-specific exceptions on HTTP errors so the caller can handle
    them uniformly without inspecting status codes.
    """
    url = f"{base_url.rstrip('/')}{_ENDPOINT_PATH}"

    try:
        response = await client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise AdapterFetchError(
            f"NewsData request timed out after {config.timeout_seconds}s"
        ) from exc
    except httpx.RequestError as exc:
        raise AdapterFetchError(f"NewsData network error: {exc}") from exc

    if response.status_code in (401, 403):
        raise AdapterAuthError(
            f"NewsData authentication failed (HTTP {response.status_code}). "
            "Check NEWSDATA_API_KEY."
        )
    if response.status_code == 429:
        raise AdapterRateLimitError(
            "NewsData rate limit exceeded (HTTP 429). "
            f"Daily limit: {config.max_articles_per_request} credits/day."
        )
    if response.status_code != 200:
        raise AdapterFetchError(
            f"NewsData returned unexpected status {response.status_code}: "
            f"{response.text[:200]}"
        )

    try:
        payload: dict[str, Any] = response.json()
    except Exception as exc:
        raise AdapterFetchError(
            f"NewsData returned non-JSON response: {response.text[:200]}"
        ) from exc

    # NewsData wraps results in {"status": "success", "results": [...]}
    if payload.get("status") != "success":
        raise AdapterFetchError(
            f"NewsData API returned non-success status: {payload.get('status')!r}. "
            f"Message: {payload.get('results', {})}"
        )

    results = payload.get("results", [])
    if not isinstance(results, list):
        raise AdapterFetchError(
            f"NewsData 'results' field is {type(results).__name__}; expected list."
        )

    return results


async def fetch_and_map(
    since: datetime,
    config: ProviderConfig,
) -> list[NewsArticle]:
    """
    Fetch articles from NewsData.io and map them to canonical NewsArticle objects.

    Makes two sequential API calls:
      1. ``country=in`` for India-focused coverage
      2. No country filter for global business/finance news

    Articles from both calls are combined; duplicates (same ``article_id``) are
    removed before returning.

    Parameters
    ----------
    since:
        Earliest publication datetime to include.  Passed as ``from_`` to the
        API where supported, and also used for local post-filtering.
    config:
        ProviderConfig with ``api_key`` and ``base_url`` populated.

    Returns
    -------
    list[NewsArticle]
        Combined, deduplicated list of canonical articles.

    Raises
    ------
    AdapterAuthError
        If the provider returns HTTP 401 or 403.
    AdapterRateLimitError
        If the provider returns HTTP 429.
    AdapterFetchError
        For all other HTTP or parse errors.
    """
    since_aware = since.replace(tzinfo=UTC) if since.tzinfo is None else since
    # NewsData uses "from_" not "from" (Python reserved word)
    since_str = since_aware.strftime("%Y-%m-%d")

    base_params: dict[str, Any] = {
        "apikey": config.api_key,
        "language": "en",
        "category": "business,politics,world,science,technology",
        "from_": since_str,
    }

    # Two call sets: India-specific + global
    call_variants: list[dict[str, Any]] = [
        {**base_params, "country": "in"},   # India pass
        {**base_params},                     # Global pass (no country filter)
    ]

    seen_ids: set[str] = set()
    all_articles: list[NewsArticle] = []

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        for i, params in enumerate(call_variants):
            call_label = "India" if i == 0 else "Global"
            logger.info("NewsData %s call — params: %s", call_label, {k: v for k, v in params.items() if k != "apikey"})

            try:
                raw_results = await _fetch_page(client, config.base_url, params, config)
            except (AdapterAuthError, AdapterRateLimitError):
                # Auth/rate-limit errors propagate immediately — both calls share
                # the same key, so continuing would just fail again.
                raise
            except AdapterFetchError as exc:
                # Log fetch errors but continue with the other call variant.
                logger.warning("NewsData %s call failed: %s", call_label, exc)
                continue

            skipped = 0
            for raw in raw_results:
                try:
                    article = _map_article(raw)
                except Exception as exc:
                    logger.warning("NewsData: error mapping article, skipping: %s", exc)
                    skipped += 1
                    continue

                if article is None:
                    skipped += 1
                    continue

                # Post-filter by publication date
                if article.published_at < since_aware:
                    skipped += 1
                    continue

                # Deduplicate by source_article_id across both calls
                dedup_key = article.source_article_id or article.url
                if dedup_key in seen_ids:
                    skipped += 1
                    continue
                seen_ids.add(dedup_key)

                all_articles.append(article)

            logger.info(
                "NewsData %s: %d raw, %d new articles, %d skipped",
                call_label,
                len(raw_results),
                len(all_articles),
                skipped,
            )

    logger.info("NewsData total: %d unique articles", len(all_articles))
    return all_articles
