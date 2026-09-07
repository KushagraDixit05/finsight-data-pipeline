# 05 — API Adapters

## Objective

Build one adapter per selected provider (Marketaux, Finnhub, NewsData.io, GDELT), each responsible only for turning that provider's raw JSON response into one or more `NewsArticle` objects.

## Why This Phase Exists

This is the concrete implementation of Rule 2 (API independence) and Rule 3 (canonical schema). After this phase, nothing downstream needs to know which API a record came from except by reading the `source` field.

## Prerequisites

`02-api-selection.md`, `04-canonical-data-model.md` completed.

## Decisions

- Each adapter exposes exactly one function: `fetch_and_map(since: datetime, config: ProviderConfig) -> list[NewsArticle]`. It performs the HTTP call(s) and the field mapping in one place, but does **not** normalize, validate, or deduplicate — that happens in later pipeline stages (`06-normalization-validation.md`, `07-deduplication.md`). Keeping mapping and cleaning separate means a mapping bug and a cleaning bug are never confused with each other.
- `since` implements the "new news" overlap window from `09-ingestion-scheduler.md` — every adapter must accept and respect it, typically as a `published_after` or `from` query parameter where the provider API supports one; where it doesn't (e.g., a provider that only returns "latest N"), the adapter fetches the latest page and lets the downstream `published_at` filtering / deduplication handle overlap.
- Category mapping is a static dict per adapter (`PROVIDER_CATEGORY_MAP`), with an explicit fallback to `markets` for anything unrecognized — this guarantees `category` is always one of the 7 valid values (`01-news-classification.md`) and adapters never invent new categories silently.
- Adapters must catch and translate provider-specific transport errors into a small shared exception type (`AdapterFetchError`, `AdapterAuthError`, `AdapterRateLimitError`) so the collector (`03-architecture.md`) can react uniformly regardless of provider (see `12-end-to-end-integration.md` for the full error-handling table).
- Each adapter stores the exact rate limit it must respect as a module-level constant with a comment citing where that number came from (Marketaux: 100 req/day free / per-plan; Finnhub: 60 calls/min free; NewsData.io: 200 credits/day free; GDELT: no documented hard limit but self-throttle to be a good citizen — see `15-api-rate-limits` section reflected into `09-ingestion-scheduler.md`).

### Per-adapter mapping notes

**`adapters/marketaux.py`**
- Endpoint: `/v1/news/all` (or equivalent "all news" search endpoint), filtered by `published_after=since`.
- Maps `entities[].symbol` → `tickers`; `entities[].name` → part of `companies`; provider's own category/industry tags → our `subcategory`; provider's `sentiment` fields → `sentiment`.
- `source_article_id` = the provider's article UUID/ID field.
- `content`: only populate if the response includes a full-body field and the pending licensing check (`02-api-selection.md`) has been closed — until then, leave `content` null and rely on `description`.

**`adapters/finnhub.py`**
- Endpoint: company news endpoint (per-symbol) called for the portfolio's active ticker universe, plus the general/market news endpoint for category `markets`.
- Maps `headline` → `title`, `summary` → `description`, `datetime` (unix seconds) → `published_at` (convert to UTC timestamptz), `related` (comma-separated tickers) → `tickers`.
- `category` = `company` when called via the per-symbol endpoint, `markets` when called via the general endpoint.
- No native `source_article_id` field confirmed — fall back to a hash of `url` as a stable pseudo-ID if the provider doesn't expose one; this does not replace `content_hash` dedup, it's just for provenance tracking.

**`adapters/newsdata.py`**
- Endpoint: `/api/1/news`, filtered with `country=in` for India-scoped calls and unfiltered/other-country calls for broader coverage, using the provider's `category` query parameter where it maps cleanly onto our 7 categories (mostly `business`→`markets`/`company`, `politics`→`government_regulation`, `world`→`geopolitical`).
- Maps `article_id` → `source_article_id`, `pubDate` → `published_at` (provider returns this in UTC per its docs — verify and convert defensively regardless), `country[]` (first element) → `country`.
- `content`: store only `description`; leave `content` null pending the licensing verification noted in `02-api-selection.md`.

**`adapters/gdelt.py`**
- Endpoint: GDELT DOC 2.0 API (`/api/v2/doc/doc`) with `mode=ArtList`, `format=json`, a keyword/theme query built from a small watchlist (macro/geopolitical/commodity keywords — e.g., "sanctions", "tariff", "central bank", "oil price", "earthquake supply chain") plus a time range, since GDELT's article-list endpoint is keyword/theme driven rather than a plain firehose.
- Maps `url` → `url`, `title` → `title`, `seendate` → `published_at` (GDELT returns this in `YYYYMMDDHHMMSS` UTC format — parse explicitly), `sourcecountry` → `country`, `tone` → part of `sentiment` (GDELT's tone score is not the same 3-bucket scale as the other providers — store it as `{"label": null, "raw_tone": <float>}` rather than force-mapping it onto Bearish/Neutral/Bullish).
- `category` = `geopolitical` by default; reclassify to `commodities_energy` or `economy_macro` if the matched theme/keyword indicates it (small keyword→category lookup table).
- `content` = **always null**. `description` may be populated from GDELT's own short snippet field if present; never longer than that.
- `source_article_id` = null (GDELT doesn't expose a stable article ID); dedup relies on URL + content hash for this provider.

## Implementation Steps

```text
Step 1 — Implement src/news/adapters/base.py with the AdapterFetchError/AdapterAuthError/AdapterRateLimitError exception classes and the ProviderConfig dataclass (api_key, base_url, timeout_seconds).
Step 2 — Implement adapters/marketaux.py per the mapping notes above.
Step 3 — Implement adapters/finnhub.py per the mapping notes above.
Step 4 — Implement adapters/newsdata.py per the mapping notes above.
Step 5 — Implement adapters/gdelt.py per the mapping notes above (no API key required).
Step 6 — Implement collectors/news_collector.py which calls all 4 adapters, catches per-adapter exceptions, and returns a combined list of NewsArticle plus a per-provider result summary (success count, error type if any) for logging.
Step 7 — Write the adapter unit tests specified in 11-testing.md before moving to normalization.
```

## Files to Create/Modify

```text
src/news/adapters/
├── __init__.py
├── base.py
├── marketaux.py
├── finnhub.py
├── newsdata.py
└── gdelt.py
src/news/collectors/
├── __init__.py
└── news_collector.py
```

## Database Changes

None in this phase.

## Configuration

```text
MARKETAUX_API_KEY=
FINNHUB_API_KEY=
NEWSDATA_API_KEY=
# GDELT_API_KEY not required — public endpoint
NEWS_COLLECTOR_TIMEOUT_SECONDS=15
```

## Testing

Adapter tests use recorded/fixture JSON responses (one fixture file per provider, checked into `tests/fixtures/`) — never live API calls in the test suite. Full spec in `11-testing.md`.

## Expected Result

Given a sample response from each provider, each adapter produces a valid `NewsArticle` list with no missing required fields and correct category mapping. The collector aggregates all 4 adapters and continues even if one raises.

## Acceptance Criteria

```text
- [ ] All 4 adapters implemented and return NewsArticle objects, not raw dicts
- [ ] Every adapter maps into exactly the 7 valid categories, never a raw provider string
- [ ] GDELT adapter never populates `content`
- [ ] Marketaux/Finnhub/NewsData.io adapters only populate `content` where explicitly justified/licensed (currently: not populated pending open items in 02-api-selection.md)
- [ ] Collector isolates adapter failures — one provider raising does not stop the others
- [ ] Adapter unit tests pass using fixture data, no live network calls in tests
```

## Dependencies / Next Phase

`06-normalization-validation.md` cleans and validates the `NewsArticle` objects the collector returns.
