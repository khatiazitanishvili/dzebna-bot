import logging
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from jobspy import scrape_jobs
from app.models import Job, SearchConfig

logger = logging.getLogger(__name__)


def run_scrape(
    db: Session,
    search_term: str,
    location: str,
    site_names: list[str],
    results_wanted: int = 20,
    is_remote: bool = False,
) -> list[Job]:
    """
    Scrape jobs from the given boards and persist new ones to MySQL.
    Returns only the newly inserted jobs (duplicates are silently skipped).
    """
    logger.info(f"Scraping '{search_term}' in '{location}' from {site_names}")

    try:
        raw = scrape_jobs(
            site_name=site_names,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            is_remote=is_remote,
            linkedin_fetch_description=True,
        )
    except Exception as e:
        logger.error(f"JobSpy scrape failed: {e}")
        return []

    if raw.empty:
        logger.info("No results returned from JobSpy")
        return []

    logger.info(f"JobSpy returned {len(raw)} raw results")

    new_jobs = []
    for _, row in raw.iterrows():
        job = _upsert_job(db, row)
        if job:
            new_jobs.append(job)

    logger.info(f"{len(new_jobs)} new jobs inserted after deduplication")
    return new_jobs


def run_scrape_for_user(db: Session, config: SearchConfig) -> list[Job]:
    """
    Convenience wrapper that takes a SearchConfig ORM object directly.
    Called by the scheduler and the /trigger endpoint.
    """
    site_names = [s.strip() for s in config.site_names.split(",")]
    return run_scrape(
        db=db,
        search_term=config.search_term,
        location=config.location or "",
        site_names=site_names,
        results_wanted=config.results_wanted,
        is_remote=config.is_remote,
    )


def _upsert_job(db: Session, row) -> Optional[Job]:
    """
    Insert a job row if it doesn't already exist (deduplication via job_id + site).
    Only accepts jobs posted within the last 24 hours.
    Returns the Job ORM object if it was newly inserted, None if it was a duplicate or too old.
    """
    job_id = str(row.get("id", "")).strip()
    site   = str(row.get("site", "")).strip()

    if not job_id or not site:
        return None

    # Check if already exists
    existing = db.query(Job).filter_by(job_id=job_id, site=site).first()
    if existing:
        return None

    # Parse date posted
    date_posted = _parse_date(row.get("date_posted"))
    
    # Filter out jobs older than 24 hours
    if date_posted:
        cutoff_date = datetime.now().date() - timedelta(days=1)
        if date_posted < cutoff_date:
            logger.debug(f"Skipping job {job_id}@{site}: posted on {date_posted}, older than 24 hours")
            return None

    # Parse salary range
    salary_min, salary_max, currency = _parse_salary(row)

    job = Job(
        job_id      = job_id,
        site        = site,
        title       = _safe_str(row.get("title")),
        company     = _safe_str(row.get("company")),
        location    = _safe_str(row.get("location")),
        is_remote   = bool(row.get("is_remote", False)),
        job_type    = _safe_str(row.get("job_type")),
        salary_min  = salary_min,
        salary_max  = salary_max,
        currency    = currency,
        description = _safe_str(row.get("description")),
        job_url     = _safe_str(row.get("job_url")),
        date_posted = date_posted,
    )

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to insert job {job_id}@{site}: {e}")
        return None


def _parse_salary(row) -> tuple[Optional[float], Optional[float], Optional[str]]:
    try:
        salary_min = float(row.get("min_amount")) if row.get("min_amount") else None
        salary_max = float(row.get("max_amount")) if row.get("max_amount") else None
        currency   = _safe_str(row.get("currency"))
        return salary_min, salary_max, currency
    except (ValueError, TypeError):
        return None, None, None


def _parse_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        from datetime import datetime
        return datetime.strptime(str(val), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _safe_str(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None