# 12 — End-to-End Integration

## Objective

Wire every previous phase together into one working pipeline, run it against real (not fixture) API credentials in a controlled dev environment, and confirm the full flow works exactly as designed from a cold start.

## Why This Phase Exists

Phases 04–11 build and unit-test each piece in isolation. This phase is the first time the whole thing runs together against live providers, which is where integration issues (an adapter's fixture didn't quite match the real API's actual current response shape, a rate limit is tighter in practice than documented, etc.) surface.

## Prerequisites

All of phases `01` through `11` completed, including the full test suite passing.

## Decisions

- This phase runs **against real API keys in a non-production environment** (a dedicated dev database, real but low-volume API calls). It is not a fixture-based test — its entire purpose is to catch the gap between "the fixture said this" and "the real API actually does this."
- Run order for the smoke test, matching the requirements' explicit flow:
  ```text
  API → normalization → deduplication → PostgreSQL
  ```
  then, if phase 10 is implemented, extended to include the embedding step.
- The full error-handling table from `09-ingestion-scheduler.md` is re-verified here against at least one real failure mode where practical (e.g., temporarily using an invalid API key for one provider to confirm `AdapterAuthError` is caught and logged without stopping the other 3 providers) — cheap to simulate and catches integration bugs unit tests with mocks can miss.

## Implementation Steps

```text
Step 1 — Provision a dev PostgreSQL database and run all migrations (001-006) from a clean state.
Step 2 — Set all required environment variables with real (free-tier) API keys for Marketaux, Finnhub, NewsData.io; GDELT needs none.
Step 3 — Run `python -m src.news.scheduler.run_ingestion` manually once.
Step 4 — Inspect news_ingestion_logs: confirm one row per provider plus one overall row, with plausible fetched/inserted/duplicate counts (not all zero, unless a provider genuinely returned nothing in the window).
Step 5 — Inspect news_articles: spot-check 5-10 rows for correct category assignment, correct UTC published_at, non-null required fields, and a properly normalized canonical_url.
Step 6 — Run the job again immediately (Step 3 repeated). Confirm articles_inserted is at or near zero on this second run and articles_duplicate accounts for the overlap, proving idempotency against real data, not just fixtures.
Step 7 — Temporarily set one provider's API key to an invalid value and re-run; confirm that provider's row logs an auth failure while the other 3 providers still successfully insert articles.
Step 8 — Restore the valid API key.
Step 9 — If phase 10 is implemented: confirm news_article_embeddings rows are created for the newly inserted articles, and run one combined vector-similarity + category-filter query against real embedded data.
Step 10 — Document any deviation discovered between a provider's real current response shape and what the adapter/fixtures assumed, and file it as a fix to the relevant adapter (05-api-adapters.md) and its fixture (11-testing.md) — do not leave the fixture silently out of date.
```

## Files to Create/Modify

None new in terms of structure — this phase may produce small fixes to existing adapter files if real API responses reveal a mismatch with fixtures.

## Database Changes

None new — uses migrations already defined.

## Configuration

Same as `09-ingestion-scheduler.md` and `10-vector-db-integration.md`, using real dev-environment API keys.

## Testing

This phase's "testing" is the manual/scripted smoke-test walkthrough in Implementation Steps above, run against real providers. It supplements, but does not replace, the automated fixture-based suite from `11-testing.md`, which remains the thing CI runs on every change.

## Expected Result

Confirmed, with real data: a full ingestion run correctly fetches from all 4 providers, normalizes and validates records, deduplicates on a second run, stores clean rows in PostgreSQL, isolates a simulated provider failure without affecting the others, and (if phase 10 is built) produces queryable embeddings.

## Acceptance Criteria

```text
- [ ] Fresh-database migration run succeeds
- [ ] First real ingestion run inserts a plausible number of articles across all 4 providers
- [ ] news_ingestion_logs rows are accurate and match what was actually inserted
- [ ] Second immediate run proves idempotency against real (not fixture) data
- [ ] Simulated provider auth failure is isolated correctly; other 3 providers unaffected
- [ ] Any fixture/adapter mismatch discovered during this phase is fixed and documented
- [ ] (If phase 10 built) embeddings generated and a combined filter+similarity query returns correct results
```

## Dependencies / Next Phase

`13-implementation-checklist.md` is the master checklist confirming every phase, including this one, is complete before considering the news pipeline "done" for MVP.
