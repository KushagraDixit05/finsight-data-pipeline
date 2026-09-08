"""
src/news/collectors/news_collector.py — Orchestrates all 4 provider adapters.

The collector is the single entry point called by the ingestion scheduler.
It runs all 4 adapter fetch calls concurrently and isolates provider failures
so that one bad adapter never stops the others.

Design decisions (03-architecture.md, 05-api-adapters.md)
──────────────────────────────────────────────────────────
  * All 4 adapters run concurrently via asyncio.gather(return_exceptions=True).
  * A provider is SKIPPED (not treated as a failure) if its API key is not
    configured — avoids counting "unconfigured" as "failed" in logs.
  * Per-provider ProviderResult captures success/failure metadata for the
    news_ingestion_logs table (08-postgresql-schema.md, 09-ingestion-scheduler.md).
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.news.adapters import base as adapter_base
from src.news.adapters import finnhub, gdelt, marketaux, newsdata
from src.news.adapters.base import ProviderConfig
from src.news.models.enums import NewsSource
from src.news.models.news_article import NewsArticle
from src.news import config as cfg

log = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """Outcome of one provider's fetch in this run."""
    source: NewsSource
    articles: list[NewsArticle] = field(default_factory=list)
    success: bool = True
    # 'auth' | 'rate_limit' | 'fetch' | 'skipped' | None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def articles_fetched(self) -> int:
        return len(self.articles)


def _make_config(api_key: str, timeout: int = None) -> ProviderConfig:
    return ProviderConfig(
        api_key=api_key,
        timeout_seconds=timeout or cfg.NEWS_COLLECTOR_TIMEOUT_SECONDS,
        max_articles_per_request=15,
    )


async def _safe_fetch(
    source: NewsSource,
    coro,
    api_key: str,
) -> ProviderResult:
    """
    Wrap a single adapter's fetch_and_map coroutine.
    Returns a ProviderResult — never raises.
    A missing API key results in a 'skipped' result, not an error.
    """
    if source != NewsSource.GDELT and not api_key:
        log.warning("%s: API key not configured, skipping provider", source.value)
        return ProviderResult(source=source, success=True, error_type="skipped",
                              error_message="API key not set")
    try:
        articles = await coro
        return ProviderResult(source=source, articles=articles, success=True)
    except adapter_base.AdapterAuthError as exc:
        log.error("%s: auth error — %s", source.value, exc)
        return ProviderResult(source=source, success=False, error_type="auth",
                              error_message=str(exc))
    except adapter_base.AdapterRateLimitError as exc:
        log.warning("%s: rate limit — %s", source.value, exc)
        return ProviderResult(source=source, success=False, error_type="rate_limit",
                              error_message=str(exc))
    except adapter_base.AdapterFetchError as exc:
        log.error("%s: fetch error — %s", source.value, exc)
        return ProviderResult(source=source, success=False, error_type="fetch",
                              error_message=str(exc))
    except Exception as exc:  # unexpected
        log.exception("%s: unexpected error", source.value)
        return ProviderResult(source=source, success=False, error_type="fetch",
                              error_message=f"Unexpected: {exc}")


async def collect_all(
    since: datetime.datetime,
) -> tuple[list[NewsArticle], list[ProviderResult]]:
    """
    Run all 4 adapters concurrently and return combined results.

    Args:
        since: UTC datetime; adapters fetch only articles published after this.

    Returns:
        (all_articles, provider_results) where:
          - all_articles is the de-duped (by url within this batch) combined list
          - provider_results gives per-provider success/failure metadata
    """
    mkt_cfg   = _make_config(cfg.MARKETAUX_API_KEY)
    fh_cfg    = _make_config(cfg.FINNHUB_API_KEY)
    nd_cfg    = _make_config(cfg.NEWSDATA_API_KEY)
    gdelt_cfg = _make_config("")  # no key needed

    tasks = [
        _safe_fetch(NewsSource.MARKETAUX, marketaux.fetch_and_map(since, mkt_cfg), cfg.MARKETAUX_API_KEY),
        _safe_fetch(NewsSource.FINNHUB,   finnhub.fetch_and_map(since, fh_cfg),    cfg.FINNHUB_API_KEY),
        _safe_fetch(NewsSource.NEWSDATA,  newsdata.fetch_and_map(since, nd_cfg),   cfg.NEWSDATA_API_KEY),
        _safe_fetch(NewsSource.GDELT,     gdelt.fetch_and_map(since, gdelt_cfg),   ""),
    ]

    results: list[ProviderResult] = await asyncio.gather(*tasks)

    # Merge and deduplicate by URL within this batch (the DB will enforce the
    # canonical_url uniqueness constraint later; this avoids wasted inserts).
    seen_urls: set[str] = set()
    all_articles: list[NewsArticle] = []
    for result in results:
        for art in result.articles:
            if art.url not in seen_urls:
                seen_urls.add(art.url)
                all_articles.append(art)

    total = sum(r.articles_fetched for r in results)
    log.info(
        "Collector: %d articles from %d providers (%d unique after batch dedup)",
        total, len([r for r in results if r.success and r.error_type != "skipped"]),
        len(all_articles),
    )
    return all_articles, list(results)
