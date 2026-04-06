from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Job, SearchConfig
from app.schemas import JobOut, ScrapeRequest, ScrapeResult
from app.services.scraper import run_scrape, run_scrape_for_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=list[JobOut])
def list_jobs(
    site:    str | None  = Query(None, description="Filter by board e.g. linkedin"),
    company: str | None  = Query(None, description="Partial company name match"),
    remote:  bool | None = Query(None, description="True = remote only"),
    limit:   int         = Query(50, le=200, description="Max results returned"),
    offset:  int         = Query(0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    Returns stored jobs with optional filters.
    Used for debugging — lets you inspect what's in the DB
    without opening Adminer.
    Example: GET /jobs/?site=linkedin&remote=true&limit=20
    """
    q = db.query(Job)

    if site:
        # Exact match on site name
        q = q.filter(Job.site == site)
    if company:
        # ilike = case-insensitive LIKE, % = wildcard on both sides
        # so "zalan" matches "Zalando"
        q = q.filter(Job.company.ilike(f"%{company}%"))
    if remote is not None:
        q = q.filter(Job.is_remote == remote)

    return (
        q.order_by(Job.scraped_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Returns a single job by its database ID.
    Raises 404 if not found — FastAPI turns HTTPException
    into a proper JSON error response automatically.
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/scrape", response_model=ScrapeResult)
def trigger_scrape(payload: ScrapeRequest, db: Session = Depends(get_db)):
    """
    One-off scrape with custom parameters.
    Useful for testing a new search term without saving a config.

    The payload comes from the request body as JSON:
    {
        "search_term": "data engineer",
        "location": "Munich, Germany",
        "results_wanted": 10
    }
    """
    site_names = [s.strip() for s in payload.site_names.split(",")]

    new_jobs = run_scrape(
        db             = db,
        search_term    = payload.search_term,
        location       = payload.location or "",
        site_names     = site_names,
        results_wanted = payload.results_wanted,
        is_remote      = payload.is_remote,
    )

    return ScrapeResult(new_jobs_found=len(new_jobs), jobs=new_jobs)


@router.post("/scrape/user/{user_id}", response_model=ScrapeResult)
def trigger_scrape_for_user(user_id: int, db: Session = Depends(get_db)):
    """
    Scrapes using all active search configs saved for a specific user.
    This is the endpoint the Telegram /trigger command calls.

    Why user_id in the URL and not the body?
    Because we're acting ON a specific resource (this user's configs),
    which is the REST convention for path parameters.
    """
    configs = (
        db.query(SearchConfig)
        .filter_by(user_id=user_id, is_active=True)
        .all()
    )

    if not configs:
        raise HTTPException(
            status_code=404,
            detail="No active search configs found for this user"
        )

    all_new_jobs = []
    for config in configs:
        # Each config may target different search terms or locations
        # We run them all and collect every new job found
        new_jobs = run_scrape_for_user(db, config)
        all_new_jobs.extend(new_jobs)

    return ScrapeResult(
        new_jobs_found=len(all_new_jobs),
        jobs=all_new_jobs
    )