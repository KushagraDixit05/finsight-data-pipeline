"""
src/news/adapters/finnhub.py — Adapter for the Finnhub.io General News API.

Provider: Finnhub  (https://finnhub.io/docs/api/market-news)
Endpoint: GET /api/v1/news?category=general&token={key}
Auth    : API key in query parameter ``token``
Tier    : Free — 60 API calls / minute (FINNHUB_RATE_LIMIT_PER_MINUTE)

Field mapping
─────────────
  Finnhub field     → NewsArticle field
  ─────────────────────────────────────
  headline          → title
  summary           → description
  datetime (unix s) → published_at  (UTC, converted from Unix timestamp)
  source            → stored in raw; NewsSource.FINNHUB always set
  url               → url
  related (tickers) → tickers  (comma-separated string → list)
  image             → image_url
  id                → *not used* — Finnhub does not expose stable article IDs
                      source_article_id = SHA-256(url)[:16] for dedup purposes

Content / licensing
───────────────────
  ``content`` is always ``None``.  Finnhub does not supply full article text
  on the free tier, and re-storing snippets from the summary field is not
  permitted by the ToS (per 02-api-selection.md).

Category
────────
  The general endpoint always maps to ``NewsCategory.MARKETS``.  Per-symbol
  calls (not implemented here) would map to ``NewsCategory.COMPANY``.

Rate-limit guard
────────────────
  This module does NOT implement a rate-limiter — that is the responsibility
  of the scheduler (Phase 06).  The adapter raises ``AdapterRateLimitError``
  if the provider returns HTTP 429, and the collector records this in the run
  summary.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.news.adapters.base import (
    AdapterAuthError,
    AdapterFetchError,
    AdapterRateLimitError,
    ProviderConfig,
    sanitize_error_msg,
)
from src.news.models import NewsArticle, NewsCategory, NewsSource, SentimentScore

logger = logging.getLogger(__name__)

# Finnhub general news endpoint — category param fixed to "general"
_ENDPOINT_PATH = "/api/v1/news"
_CATEGORY_PARAM = "general"


def _parse_unix_ts(unix_seconds: int | float) -> datetime:
    """Convert a Unix timestamp (seconds) to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(unix_seconds, tz=UTC)


def _url_hash_id(url: str) -> str:
    """
    Derive a short, stable source_article_id from the article URL.

    Finnhub does not expose a stable numeric/string article ID on the general
    news endpoint (the ``id`` field in responses is an internal integer that
    can change between API versions).  We use the first 16 hex chars of the
    SHA-256 of the URL, which gives a collision probability of ~1 in 10^19 for
    the volume of articles we handle.
    """
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_tickers(related: str | None) -> list[str] | None:
    """
    Split Finnhub's comma-separated ``related`` field into a ticker list.

    Returns ``None`` (not an empty list) when the field is absent or blank,
    so the downstream model validator can distinguish "no data" from "empty".
    """
    if not related or not related.strip():
        return None
    return [t.strip().upper() for t in related.split(",") if t.strip()]


def _map_article(raw: dict[str, Any]) -> NewsArticle | None:
    """
    Map a single Finnhub JSON article object to a canonical NewsArticle.

    Returns ``None`` if essential fields (url, headline) are missing so the
    caller can skip malformed records without crashing the whole batch.
    """
    url: str = raw.get("url", "").strip()
    title: str = raw.get("headline", "").strip()

    if not url or not title:
        logger.debug("Skipping Finnhub record — missing url or headline: %s", raw)
        return None

    unix_ts = raw.get("datetime")
    if unix_ts is None:
        # Fall back to now so the record isn't lost; log for visibility.
        logger.warning("Finnhub record has no datetime field, using now(UTC): %s", url)
        published_at = datetime.now(UTC)
    else:
        try:
            published_at = _parse_unix_ts(unix_ts)
        except (OSError, OverflowError, ValueError) as exc:
            logger.warning("Cannot parse Finnhub datetime %r for %s: %s", unix_ts, url, exc)
            published_at = datetime.now(UTC)

    return NewsArticle(
        source=NewsSource.FINNHUB,
        url=url,
        title=title,
        description=raw.get("summary") or None,  # empty string → None
        content=None,  # Never stored — licensing constraint
        image_url=raw.get("image") or None,
        published_at=published_at,
        fetched_at=datetime.now(UTC),
        category=NewsCategory.MARKETS,  # General endpoint → MARKETS always
        source_article_id=_url_hash_id(url),
        tickers=_parse_tickers(raw.get("related")),
        sentiment=None,  # Finnhub general news does not supply sentiment
    )


async def fetch_and_map(
    since: datetime,
    config: ProviderConfig,
) -> list[NewsArticle]:
    """
    Fetch articles from Finnhub's general news endpoint and map to canonical form.

    The ``since`` parameter is advisory for Finnhub: the general endpoint does
    not support a ``from`` date filter on the free tier.  We request the latest
    batch and post-filter locally by ``published_at >= since``.

    Parameters
    ----------
    since:
        Earliest publication datetime to include.  Articles published before
        this threshold are silently discarded after fetch.
    config:
        ProviderConfig with at minimum ``api_key`` and ``base_url`` populated.
        The base_url should be ``https://finnhub.io`` (or the test mock URL).

    Returns
    -------
    list[NewsArticle]
        Zero or more canonical articles published on or after ``since``.

    Raises
    ------
    AdapterAuthError
        If the provider returns HTTP 401 or 403.
    AdapterRateLimitError
        If the provider returns HTTP 429.
    AdapterFetchError
        For all other HTTP errors or network failures.
    """
    base = config.base_url if config.base_url else "https://finnhub.io"
    url = f"{base.rstrip('/')}{_ENDPOINT_PATH}"
    params: dict[str, str | int] = {
        "category": _CATEGORY_PARAM,
        "token": config.api_key,
        "minId": 0,  # fetch latest; free-tier ignores date range params
    }

    logger.info("Fetching Finnhub general news from %s", url)

    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise AdapterFetchError(
            f"Finnhub request timed out after {config.timeout_seconds}s"
        ) from exc
    except httpx.RequestError as exc:
        err_msg = sanitize_error_msg(str(exc), config)
        raise AdapterFetchError(f"Finnhub network error: {err_msg}") from exc

    # ── HTTP error handling ───────────────────────────────────────────────────
    if response.status_code in (401, 403):
        raise AdapterAuthError(
            f"Finnhub authentication failed (HTTP {response.status_code}). "
            "Check FINNHUB_API_KEY."
        )
    if response.status_code == 429:
        raise AdapterRateLimitError(
            "Finnhub rate limit exceeded (HTTP 429). "
            f"Limit: {config.max_articles_per_request} calls/min."
        )
    if response.status_code != 200:
        err_msg = sanitize_error_msg(response.text[:200], config)
        raise AdapterFetchError(
            f"Finnhub returned unexpected status {response.status_code}: "
            f"{err_msg}"
        )

    # ── Parse and map ─────────────────────────────────────────────────────────
    try:
        raw_articles: list[dict[str, Any]] = response.json()
    except Exception as exc:
        raise AdapterFetchError(
            f"Finnhub returned non-JSON response: {response.text[:200]}"
        ) from exc

    if not isinstance(raw_articles, list):
        raise AdapterFetchError(
            f"Finnhub returned unexpected payload type {type(raw_articles).__name__}; "
            "expected a JSON array."
        )

    articles: list[NewsArticle] = []
    skipped = 0

    # Ensure since is timezone-aware for comparison
    since_aware = since.replace(tzinfo=UTC) if since.tzinfo is None else since

    for raw in raw_articles:
        try:
            article = _map_article(raw)
        except Exception as exc:
            # Never let a single bad record abort the whole batch.
            logger.warning("Finnhub: error mapping article, skipping: %s", exc)
            skipped += 1
            continue

        if article is None:
            skipped += 1
            continue

        # Post-filter: discard articles published before our since window
        if article.published_at < since_aware:
            skipped += 1
            continue

        articles.append(article)

    logger.info(
        "Finnhub: %d articles fetched, %d mapped, %d skipped",
        len(raw_articles),
        len(articles),
        skipped,
    )
    return articles
