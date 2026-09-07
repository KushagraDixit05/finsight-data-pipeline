# 06 — Normalization, Cleaning & Validation

## Objective

Define and implement the deterministic transformation layer that takes an adapter's raw `NewsArticle` and produces a cleaned, normalized, validated `NewsArticle` ready for deduplication and storage.

## Why This Phase Exists

Adapters map field-to-field; they don't clean text, resolve timezones, or reject malformed records. That logic needs to live in one shared, provider-agnostic place so cleaning rules are applied identically no matter which of the 4 providers produced the record (Rule 2, Rule 3).

## Prerequisites

`04-canonical-data-model.md`, `05-api-adapters.md` completed.

## Decisions

### Normalization rules (deterministic, in this exact order)

1. **Date/time normalization**: parse every provider's `published_at` into a timezone-aware UTC `datetime`. Never trust an implicit-timezone string — if a provider's docs don't explicitly state UTC, treat the timestamp as UTC only after confirming via adapter-level testing against known articles; otherwise log a warning and still store it (better to have an approximately-right timestamp than to drop the article). `fetched_at` is always set by our own system clock in UTC, never parsed from a provider.
2. **Timezone handling**: all stored timestamps are UTC. Any timezone-local display happens at the API/frontend layer, never in this pipeline.
3. **Empty/null handling**: empty strings (`""`) are normalized to `None` for all optional fields before validation — an empty string is not meaningfully different from "not provided," and treating them differently would create inconsistent query results later.
4. **Text cleaning**: strip HTML tags from `title`, `description`, and `content` (some providers embed `<b>`/`<em>` highlight markup in search results). Collapse repeated whitespace. Strip leading/trailing whitespace. Do not strip punctuation or alter casing — that would damage readability and hurt embedding quality.
5. **HTML removal**: use a proper HTML-tag stripper (e.g., a small regex for simple tag removal, or `bleach`/`lxml` if already a dependency) rather than naive string replace, to avoid mangling text that legitimately contains `<`/`>` characters.
6. **Source normalization**: map the adapter's `source` value to the exact `news_sources.id` values seeded in `08-postgresql-schema.md` (`marketaux`, `finnhub`, `newsdata`, `gdelt`) — this should already be correct coming out of the adapter, but this stage is where it's asserted, not assumed.
7. **Category mapping**: assert `category` is one of the 7 enum values — this is a re-check, not a re-mapping (the adapter already mapped it); if this check ever fails, it's a bug in the adapter, and the record is rejected with a loud log rather than silently coerced.
8. **Country normalization**: uppercase and validate against ISO 3166-1 alpha-2; anything not matching a known 2-letter code is set to `None` rather than stored as garbage.
9. **Language normalization**: lowercase and validate against ISO 639-1; unknown values set to `None`.
10. **URL normalization**: lowercase the scheme and host, strip common tracking query parameters (`utm_*`, `fbclid`, `gclid`, `ref`, `src`), remove a trailing slash, and remove the URL fragment (`#...`). This normalized form becomes `canonical_url` and is the basis for Level-1 deduplication (`07-deduplication.md`) — two URLs that only differ by tracking parameters must normalize to the same `canonical_url`.
11. **Author normalization**: trim whitespace; normalize obviously-placeholder values (`"Staff"`, `""`, `"Admin"`, provider-specific bylines like `"Reuters Staff"` are left as-is — only truly empty/whitespace-only values become `None`).

### Validation rules (after normalization)

A record is **rejected** (not stored, logged with reason) if, after normalization:
- Any required field (`source`, `url`, `title`, `published_at`, `fetched_at`, `category`) is still missing or empty.
- `url` does not parse as a valid absolute URL.
- `published_at` is more than 24 hours in the future (clock-skew/bad-data guard) or older than a configurable historical floor (default: reject anything older than 30 days on first ingestion, to avoid silently backfilling a huge historical batch from a provider that returns old data by default — this floor does not apply to `since`-filtered "new news" runs, only as a sanity guard).
- `title` is empty after HTML stripping and whitespace collapse.

A record is **kept with a logged warning** (not rejected) if:
- `language` or `country` could not be normalized (set to `None`).
- `description`/`content`/`author`/`image_url` are missing (all optional).

### Determinism requirement

Every rule above is a pure function of its input — no external state, no randomness, no network calls. This is required so that re-running normalization on the same raw record always produces the same canonical record, which is what makes deduplication and idempotent re-runs (`13-idempotency`, reflected in `09-ingestion-scheduler.md`) actually reliable.

## Implementation Steps

```text
Step 1 — Implement normalizers/text.py: strip_html(text), clean_whitespace(text).
Step 2 — Implement normalizers/datetime_utils.py: to_utc(value, source_hint) -> datetime | None.
Step 3 — Implement normalizers/url.py: normalize_url(url) -> str.
Step 4 — Implement normalizers/geo.py: normalize_country(code), normalize_language(code).
Step 5 — Implement normalizers/pipeline.py: normalize(article: NewsArticle) -> NewsArticle, calling steps 1-4 in the documented order and computing content_hash (see 07-deduplication.md) as the final step.
Step 6 — Implement normalizers/validate.py: validate(article: NewsArticle) -> ValidationResult (ok: bool, reason: str | None), applying the rejection rules above.
Step 7 — Wire normalize() -> validate() into the collector's per-record loop, routing rejected records to the ingestion log rather than raising and stopping the batch.
```

## Files to Create/Modify

```text
src/news/normalizers/
├── __init__.py
├── text.py
├── datetime_utils.py
├── url.py
├── geo.py
├── pipeline.py
└── validate.py
```

## Database Changes

None in this phase.

## Configuration

```text
NEWS_MAX_ARTICLE_AGE_DAYS=30   # historical floor for first-time ingestion sanity check
```

## Testing

```text
- Unit test: HTML tags stripped from title/description/content without mangling plain text.
- Unit test: URL normalization strips tracking params and produces identical canonical_url for two URLs differing only by utm_* params.
- Unit test: timestamps from each provider's known format parse correctly to UTC.
- Unit test: missing required field after normalization -> validation rejects with a clear reason.
- Unit test: empty string optional fields normalize to None, not stored as "".
- Unit test: unrecognized country/language code normalizes to None rather than raising.
```

## Expected Result

Every `NewsArticle`, regardless of source provider, has been through the identical cleaning and validation logic before it's considered for deduplication and storage. Malformed records are rejected with a logged, human-readable reason rather than crashing the batch.

## Acceptance Criteria

```text
- [ ] All 11 normalization rules implemented in the specified order
- [ ] Validation rejects records missing required fields, with logged reasons
- [ ] Normalization is provably deterministic (same input -> same output) via a repeatability unit test
- [ ] One malformed record in a batch does not stop processing of the rest of the batch
- [ ] All normalization/validation unit tests pass
```

## Dependencies / Next Phase

`07-deduplication.md` operates on normalized, validated records — specifically it depends on `canonical_url` and `content_hash` being already computed by this phase.
