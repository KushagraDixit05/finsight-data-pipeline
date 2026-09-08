"""
src/news/scheduler/run_ingestion.py — The main ingestion entrypoint.
"""
import asyncio
import logging
import sys
from datetime import datetime

from src.news.database.session import get_db, SessionLocal
from src.news.scheduler.lock import acquire_lock, release_lock
from src.news.scheduler.window import compute_fetch_window
from src.news.collectors.news_collector import collect_all
from src.news.normalizers.pipeline import normalize
from src.news.normalizers.validate import validate
from src.news.deduplication.check import check_duplicate
from src.news.database.repository import insert_article, log_ingestion_run
from src.news.normalizers.datetime_utils import UTC

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def run_ingestion_job():
    db = SessionLocal()
    run_started_at = datetime.now(UTC)
    
    if not acquire_lock(db):
        return 0

    try:
        window_since = compute_fetch_window(db)
        log.info(f"Fetching news since: {window_since}")
        
        all_articles, provider_results = await collect_all(since=window_since)
        
        total_inserted = 0
        total_duplicate = 0
        total_failed_validation = 0
        
        for article in all_articles:
            # Normalize
            normalized = normalize(article)
            
            # Validate
            val_result = validate(normalized)
            if not val_result.ok:
                log.warning(f"Validation failed for {normalized.url}: {val_result.reason}")
                total_failed_validation += 1
                continue
                
            # Dedup check
            dedup_result = check_duplicate(db, normalized)
            if dedup_result.is_duplicate:
                log.debug(f"Duplicate article: {dedup_result.reason}")
                total_duplicate += 1
                continue
                
            # Insert
            if insert_article(db, normalized):
                total_inserted += 1
            else:
                total_duplicate += 1
                
        run_finished_at = datetime.now(UTC)
        overall_status = "success"
        
        # Determine overall status
        failed_providers = [r for r in provider_results if not r.success]
        success_providers = [r for r in provider_results if r.success and r.error_type != "skipped"]
        
        if failed_providers and success_providers:
            overall_status = "partial_failure"
        elif failed_providers and not success_providers:
            overall_status = "failure"
            
        # Log per provider
        for result in provider_results:
            log_ingestion_run(
                db=db,
                source=result.source.value,
                run_started_at=run_started_at,
                run_finished_at=run_finished_at,
                status="success" if result.success else "failure",
                articles_fetched=result.articles_fetched,
                error_summary=result.error_message
            )
            
        # Log overall
        log_ingestion_run(
            db=db,
            source=None,
            run_started_at=run_started_at,
            run_finished_at=run_finished_at,
            status=overall_status,
            articles_fetched=len(all_articles),
            articles_inserted=total_inserted,
            articles_duplicate=total_duplicate,
            articles_failed_validation=total_failed_validation
        )
        
        log.info(f"Ingestion complete: {total_inserted} inserted, {total_duplicate} duplicates, {total_failed_validation} invalid.")
        return 0
        
    except Exception as e:
        log.exception("Unexpected error during ingestion run.")
        return 1
    finally:
        release_lock(db)
        db.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(run_ingestion_job()))
