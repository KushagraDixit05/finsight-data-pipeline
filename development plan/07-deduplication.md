# 07 — Duplicate / Redundant News Detection

## Objective

Design and implement the layered deduplication strategy so the same real-world article, whether returned by one provider once or by multiple providers, is stored as a single `news_articles` row.

## Why This Phase Exists

With 4 providers polled every 2 hours, the same Reuters/PTI/ANI wire story routinely appears from more than one API. Storing it multiple times pollutes search results, wastes embedding cost, and breaks any later "how many articles mention X" reasoning.

## Prerequisites

`06-normalization-validation.md` completed (this phase consumes its `canonical_url` and `content_hash` outputs).

## Decisions

### The four levels, and how MVP handles each

**Level 1 — Exact URL match.**
Two articles with the same `canonical_url` (normalized in `06-normalization-validation.md`: lowercased host, tracking params stripped, trailing slash/fragment removed) are the same article. Enforced with a **unique database constraint** on `canonical_url`. This is the cheapest, most reliable signal and catches the common case of two providers linking to the identical publisher URL.

**Level 2 — Source + source article ID match.**
If the *same provider* returns the *same article ID* again (e.g., a re-run inside the overlap window, or the provider re-serves the same item across pages), it's the same article. Enforced with a **unique partial database constraint** on `(source, source_article_id)` where `source_article_id IS NOT NULL`. This does not catch cross-provider duplicates — it catches same-provider re-fetch, which is primarily an idempotency safeguard (`13-idempotency`, `09-ingestion-scheduler.md`), not a cross-source dedup layer.

**Level 3 — Content/title hash.**
Two articles with different URLs (e.g., a provider mirrors the wire story on its own domain) but the same normalized title, same source-of-truth wire agency, and the same published hour are treated as duplicates. `content_hash = sha256(normalized_title + "|" + source + "|" + published_at.strftime("%Y-%m-%d-%H"))`, computed in the normalization pipeline. Enforced with a **unique database constraint** on `content_hash`. Deliberately scoped to `source` (not cross-source) plus an hour-bucketed timestamp, because: (a) hashing purely on title text without a time component would falsely collide on recurring headlines (e.g., "Sensex ends higher" appears most trading days), and (b) requiring exact provider match at this level keeps Level 3 conservative and false-positive-resistant; true cross-provider "same story, different wording" duplicates are handled by Level 4.

**Level 4 — Near-duplicate / semantic detection.**
Example from the requirements: "RBI keeps repo rate unchanged" vs. "RBI leaves repo rate unchanged" — different URLs, different providers, different exact wording, same event.

**Decision: defer Level 4 past MVP.** Reasoning:
- It requires either an embedding-similarity comparison (needs the embedding pipeline from `10-vector-db-integration.md` to exist first and to run *before* the dedup decision, inverting the current pipeline order) or a separate lightweight text-similarity technique (e.g., shingled Jaccard similarity on title tokens), which is a real engineering component with a tunable threshold that needs a labeled evaluation set to get right — building it now, without data to tune against, risks either over-merging distinct stories or under-catching real duplicates.
- MVP correctness does not require it: storing "RBI keeps repo rate unchanged" and "RBI leaves repo rate unchanged" as two rows is not *wrong* — it's suboptimal (mildly redundant context for the RAG layer later) but does not corrupt any downstream reasoning, unlike storing the literal same article twice under Levels 1-3, which would actively double-count and pollute results.
- **The schema is built to support it later without a migration**: `news_articles.duplicate_of_id` (self-referencing, nullable) exists from `08-postgresql-schema.md` onward. When Level 4 is implemented, it becomes a batch job that finds high-similarity pairs among already-stored articles and sets `duplicate_of_id` on the newer one — an additive process, not a pipeline redesign.

### Distinguishing the four duplicate/near-duplicate scenarios from the requirements

| Scenario | Example | MVP handling |
|---|---|---|
| Exact duplicate | Same URL from 2 providers | Level 1 — rejected at insert, only one row ever created |
| Same story, different publisher | Reuters wire picked up by 2 outlets with different URLs, same content | Not caught in MVP (would need Level 4); acceptable per decision above |
| Updated version of an article | Same URL, title/content edited after publication, provider re-serves it | `canonical_url` is stable, so this hits the Level 1 unique constraint on **insert** — MVP behavior is **skip**, not update (see below); flagged as a deferred enhancement |
| Different articles covering the same event | Two independently-written articles about the same RBI decision from different agencies | Not a duplicate — both are legitimately stored; this is normal multi-source coverage, not something to deduplicate |

### Insert-time behavior: skip-on-conflict, not upsert, for MVP

When Level 1, 2, or 3 detects a conflict, the pipeline **skips the insert** and logs it as a duplicate in `news_ingestion_logs`; it does not update the existing row with the new payload. Reasoning: implementing "is this actually a meaningful content update vs. just a re-fetch of the same thing" correctly requires comparing the new content against the old, which reopens near-duplicate-style complexity. Skip-on-conflict is simple, safe, and never loses data (the original article is still there); update-on-conflict is a defensible future enhancement once there's a real signal for "this is a materially updated version," not before.

## Implementation Steps

```text
Step 1 — Implement deduplication/check.py: check_duplicate(article: NewsArticle, db_session) -> DuplicateCheckResult, which queries for existing rows matching canonical_url, then (source, source_article_id), then content_hash, in that order (cheapest/most-selective first), short-circuiting on the first match.
Step 2 — Wire the 3 unique database constraints (canonical_url, (source, source_article_id) partial, content_hash) in 08-postgresql-schema.md — these are the actual source of truth; the application-level check in Step 1 exists to fail gracefully with a clean log entry instead of a raw database IntegrityError surfacing to the operator.
Step 3 — In the insertion function (database/repository.py, built in 08-postgresql-schema.md), catch the database's unique-violation exception as a safety net even if the application-level check somehow misses a race condition (e.g., two near-simultaneous adapter calls), and treat it identically to an application-level duplicate: log and skip, don't crash the batch.
Step 4 — Add duplicate_of_id (nullable, self-referencing FK) to the news_articles table now, unused until Level 4 is built, so no future migration is needed to add it.
```

## Files to Create/Modify

```text
src/news/deduplication/
├── __init__.py
└── check.py
```

## Database Changes

(Full DDL in `08-postgresql-schema.md`; summarized here since this phase drives the requirements)

```text
- UNIQUE constraint on news_articles.canonical_url
- UNIQUE constraint on news_articles (source, source_article_id) WHERE source_article_id IS NOT NULL
- UNIQUE constraint on news_articles.content_hash
- Nullable self-referencing FK: news_articles.duplicate_of_id -> news_articles.id
```

## Configuration

None specific to this phase.

## Testing

```text
- Test: inserting the same canonical_url twice -> second insert is skipped, logged as duplicate, no exception propagates.
- Test: same source + source_article_id twice -> second insert skipped.
- Test: same content_hash from the same source within the same published hour -> second insert skipped.
- Test: two articles about the same event but genuinely different URLs, sources, and titles -> both inserted (not falsely deduplicated).
- Test: a simulated race (two near-simultaneous inserts of the same canonical_url) is handled by the database unique constraint without corrupting the table or crashing the job.
```

## Expected Result

No two rows in `news_articles` ever share a `canonical_url`, a `(source, source_article_id)` pair, or a `content_hash`. Cross-provider "same story, different wording" duplicates are accepted as a known, documented MVP limitation, with the schema ready for a future Level 4 pass.

## Acceptance Criteria

```text
- [ ] check_duplicate() implemented, checking Levels 1-3 in order
- [ ] All 3 unique constraints created and enforced at the database level, not just the application level
- [ ] Duplicate detection at insert time never raises an unhandled exception — always logs and continues
- [ ] duplicate_of_id column exists and is documented as reserved for future Level 4 work
- [ ] Deduplication test suite (5 cases above) passes
```

## Dependencies / Next Phase

`08-postgresql-schema.md` implements the constraints this phase specifies.
