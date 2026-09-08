"""
src/news/scheduler/lock.py — PostgreSQL advisory lock for idempotency.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

log = logging.getLogger(__name__)

# A fixed constant for the advisory lock key.
NEWS_ADVISORY_LOCK_KEY = 487219

def acquire_lock(db: Session, key: int = NEWS_ADVISORY_LOCK_KEY) -> bool:
    """
    Acquire a PostgreSQL advisory lock.
    Returns True if acquired, False if already held.
    """
    result = db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar()
    if result:
        log.debug(f"Advisory lock {key} acquired.")
        return True
    else:
        log.info(f"Advisory lock {key} could not be acquired. Another run is likely in progress.")
        return False

def release_lock(db: Session, key: int = NEWS_ADVISORY_LOCK_KEY) -> None:
    """
    Release a PostgreSQL advisory lock.
    """
    db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    log.debug(f"Advisory lock {key} released.")
