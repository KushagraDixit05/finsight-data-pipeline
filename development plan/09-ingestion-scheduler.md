# 09 — Ingestion Scheduler, Idempotency & "New News" Strategy

## Objective

Implement the job that cron invokes every 2 hours: acquire a lock, determine the fetch window, call the collector, run normalization → validation → deduplication → insert for each record, log the run, and release the lock — safely, even under overlapping invocations, partial API failures, or accidental re-runs.

## Why This Phase Exists

This is where every earlier phase gets wired into one operational job, and where the requirements' Sections 4, 12, 13, 14, and 15 (frequency, error handling, idempotency, new-news strategy, rate limits) get concrete answers.

## Prerequisites

`05-api-adapters.md` through `08-postgresql-schema.md` completed.

## Decisions

### Is cron sufficient? Yes.

Confirmed in `03-architecture.md`: cron (or the platform-equivalent scheduled-job feature) invoking a Python entrypoint every 2 hours is sufficient at this call volume. No background job framework is introduced.

### Preventing overlapping runs

A **PostgreSQL advisory lock** (`pg_try_advisory_lock(<fixed key>)`) is acquired at the very start of `run_ingestion.py`, before any adapter is called. If the lock is already held (a previous run is still in progress — e.g., a slow API stalled past the 2-hour mark), the new invocation logs `"skipped: previous run still in progress"` to `news_ingestion_logs` and exits immediately with status code 0 (not an error — this is expected, graceful behavior, not a failure). The lock is released in a `finally` block, and also automatically releases if the database session/connection drops (e.g., the process crashes), so a hard crash can never leave the pipeline permanently locked.

### "New news" strategy — overlap window, not a hard cutoff

Naively fetching only `last_run_time → now` is exactly the bug called out in the requirements: a wire service can add an article to its index a few minutes *after* its `published_at` timestamp, meaning a strict `10:00 → 12:00` window at 12:00 can permanently miss an article published at 09:58 but indexed by the provider at 10:05.

**Decision**: each run fetches `since = last_successful_run_started_at - OVERLAP_WINDOW`, where `OVERLAP_WINDOW` defaults to **30 minutes**. This means every 2-hour run re-requests the last 2.5 hours of news from each provider. This is safe and cheap because deduplication (`07-deduplication.md`) guarantees the re-fetched portion is skipped as duplicates at insert time — the overlap costs a small amount of wasted API quota and CPU on duplicate-checking, not correctness risk or storage bloat.

`last_successful_run_started_at` is read from `news_ingestion_logs` (`get_last_successful_run()`), using **`run_started_at` of the last `success`-status run**, not `run_finished_at` — using the start time (not the finish time) of the previous run is what correctly accounts for the provider's own indexing delay, since the delay is relative to when we last *asked*, not when we finished processing what we got back.

**First-ever run** (no prior successful run in the log table): `since = now - NEWS_MAX_ARTICLE_AGE_DAYS` (default 30 days, from `06-normalization-validation.md`), giving a bounded initial backfill rather than an unbounded one.

**Clock differences**: because `OVERLAP_WINDOW` and the historical floor are both generous, and because the actual "is this new" decision is ultimately enforced by the database's unique constraints (not by trusting the time window as a hard filter), the fetch window only needs to be "wide enough to be safe," not perfectly precise — precision is deduplication's job, not the scheduler's.

### Error handling

| Failure | Behavior |
|---|---|
| One provider's API is unavailable (connection error/timeout) | Caught in `adapters/base.py`; that provider's `AdapterFetchError` is logged in `news_ingestion_logs` (one row per source per run); the other 3 providers still run |
| Provider returns HTTP 429 | Caught as `AdapterRateLimitError`; the adapter does **not** retry immediately within the same run (retrying into an active rate limit makes it worse); it's logged, and the next scheduled run (2 hours later) naturally retries via the overlap window |
| Provider returns malformed JSON | Caught as `AdapterFetchError` at the JSON-parse step; logged; that provider's batch for this run is treated as empty, not partially processed |
| Provider returns zero articles | Not an error — logged as a normal run with `articles_fetched = 0` for that source |
| Provider authentication fails (401/403) | Caught as `AdapterAuthError`; logged with high visibility (this is a configuration problem, not a transient one — it will keep failing every run until fixed, so the log entry should be easy to alert on, e.g., a distinct `status` value or a clearly prefixed `error_summary`) |
| Database is unavailable | The whole job fails fast — this is caught at the top level of `run_ingestion.py`; the advisory lock is released, a best-effort log write is attempted (may itself fail if the DB is truly down, which is acceptable — the next run's absence of a `success` log entry is itself the signal something is wrong), and the process exits non-zero so cron's own failure visibility (mail/log) picks it up |
| Duplicate article detected | Not an error — logged as `articles_duplicate` count, per `07-deduplication.md` |
| One API succeeds while another fails | Job overall status is `partial_failure` if at least one provider succeeded and at least one failed; `success` if all succeeded; `failure` only if the job couldn't run at all (e.g., DB unavailable, or the advisory lock step itself errored) |
| Scheduler runs while a previous job is still running | Advisory lock causes immediate, logged, non-error skip (see above) |

### Retrying failed APIs

Within a single run, each adapter gets **one attempt** with a short built-in HTTP retry only for transient network-level failures (e.g., a single connection reset) — a small, bounded retry (2 attempts, short backoff) inside the HTTP client, not a business-logic-level retry loop. No retry is attempted for 429s or 4xx auth errors (retrying those is either useless or harmful). The real "retry" mechanism for a fully-failed provider is simply **the next scheduled run**, 2 hours later, whose overlap window will naturally pick up whatever was missed — this keeps the retry story simple and avoids building a separate retry-queue system for a job that already runs every 2 hours.

### Logging

Two levels of log rows per run, both in `news_ingestion_logs`:
- One row per provider (`source` set), recording that provider's fetch/insert/duplicate/failure counts.
- One row with `source = NULL` representing the overall job run (aggregate counts, overall `status`).

Application logs (stdout/stderr, captured by cron into a log file per `03-architecture.md`'s crontab line) additionally record human-readable detail for debugging — the database log rows are the structured, queryable record; the log file is the raw trace.

### Idempotency

Running the job twice in immediate succession (e.g., an operator manually re-invokes it right after a scheduled run) must not create duplicate rows. This is guaranteed by the combination of:
1. The advisory lock preventing true *concurrent* overlap.
2. The unique database constraints (`07-deduplication.md`, `08-postgresql-schema.md`) making a second insert of the same article a no-op (caught and logged, not an error) even for a *sequential* re-run after the lock is released.

No separate "idempotency key" mechanism is needed beyond what deduplication already provides — the unique constraints on `canonical_url`/`(source, source_article_id)`/`content_hash` **are** the idempotency guarantee.

## API Rate Limits (respected by the collector, not assumed)

| Provider | Documented limit (verify before production) | How the collector respects it |
|---|---|---|
| Marketaux | 100 req/day (free) / plan-dependent | One `/news/all` call per run covers the window in as few paginated requests as the `articles_per_request` cap allows (3/req on free tier — MVP volume is low enough this is acceptable; revisit page size on paid tier) |
| Finnhub | 60 calls/minute (free) | Adapter batches per-symbol company-news calls with a small delay between calls, staying well under 60/min even for a moderate ticker watchlist |
| NewsData.io | 200 credits/day (free) | One or two calls per run (India-scoped + general), well under budget at 12 runs/day |
| GDELT | No hard documented limit on the public DOC API; self-throttled | Collector adds a fixed small delay between GDELT queries and limits the number of keyword/theme queries per run to avoid being a bad citizen (per GDELT's own guidance to respect rate limits and not degrade service availability) |

All limits are read from `config.py` constants with a comment citing this table, **not hardcoded inline in adapter logic**, so they can be updated the moment a plan changes without touching adapter code.

## Implementation Steps

```text
Step 1 — Implement scheduler/lock.py: acquire_lock(session) / release_lock(session) wrapping pg_try_advisory_lock / pg_advisory_unlock.
Step 2 — Implement scheduler/window.py: compute_fetch_window(session) -> datetime, implementing the overlap-window / first-run logic above.
Step 3 — Implement scheduler/run_ingestion.py as the single entrypoint: acquire lock -> compute window -> call collector -> for each returned article: normalize -> validate -> dedup-check -> insert -> aggregate counts -> write per-source and overall news_ingestion_logs rows -> release lock.
Step 4 — Ensure run_ingestion.py exits 0 on success/partial_failure/skip, and non-zero only on total failure (DB unavailable / lock mechanism itself erroring), so cron's exit-code-based alerting is meaningful.
Step 5 — Add the crontab entry (documented in 03-architecture.md) to the deployment.
Step 6 — Run the job manually twice in a row locally against a test database and confirm zero duplicate rows are created (idempotency smoke test).
```

## Files to Create/Modify

```text
src/news/scheduler/
├── __init__.py
├── lock.py
├── window.py
└── run_ingestion.py
```

## Database Changes

None new — this phase consumes tables built in `08-postgresql-schema.md`.

## Configuration

```text
DATABASE_URL=postgresql://user:password@localhost:5432/finsight
MARKETAUX_API_KEY=
FINNHUB_API_KEY=
NEWSDATA_API_KEY=
NEWS_INGESTION_INTERVAL_HOURS=2
NEWS_OVERLAP_WINDOW_MINUTES=30
NEWS_MAX_ARTICLE_AGE_DAYS=30
NEWS_ADVISORY_LOCK_KEY=487219  # any fixed constant, unique within the DB's lock-key space
MARKETAUX_RATE_LIMIT_PER_DAY=100
FINNHUB_RATE_LIMIT_PER_MINUTE=60
NEWSDATA_RATE_LIMIT_PER_DAY=200
```

## Testing

Full spec in `11-testing.md`; scheduler-specific cases:
```text
- Test: job executes end-to-end against fixture-backed adapters and inserts expected rows.
- Test: a failed adapter (simulated) does not stop the other adapters' processing.
- Test: running the job twice in a row produces zero duplicate rows (idempotency).
- Test: attempting to acquire the advisory lock while it's already held results in a graceful, logged skip, not an error.
- Test: compute_fetch_window() returns the historical-floor window on first run (no prior log rows) and the overlap-window calculation on subsequent runs.
```

## Expected Result

A single command (`python -m src.news.scheduler.run_ingestion`), safe to run on a 2-hour cron schedule or manually at any time, that reliably and idempotently ingests news from all 4 providers with full fault isolation and an auditable log trail.

## Acceptance Criteria

```text
- [ ] Advisory lock prevents concurrent overlapping runs
- [ ] Overlap-window "new news" strategy implemented exactly as specified
- [ ] All error-handling behaviors in the table above implemented and logged
- [ ] Rate limits read from configuration, not hardcoded
- [ ] Idempotency smoke test (run twice, zero duplicates) passes
- [ ] Crontab entry documented and working in a test environment
```

## Dependencies / Next Phase

`10-vector-db-integration.md` adds the embedding step, which runs after this job's insert step completes (decoupled, per `03-architecture.md`).
