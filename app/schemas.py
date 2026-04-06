from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


# ── Search Config ──────────────────────────────────────────────

class SearchConfigCreate(BaseModel):
    """
    What the Telegram bot sends when creating a search config.
    All fields have sensible defaults so the bot only needs to
    supply search_term and location at minimum.
    """
    search_term:    str
    location:       Optional[str] = None
    is_remote:      bool = False
    results_wanted: int  = 20
    site_names:     str  = "linkedin,indeed,glassdoor"


class SearchConfigOut(SearchConfigCreate):
    """
    What the API returns when reading a search config back.
    Extends SearchConfigCreate with the DB-generated fields.
    model_config tells Pydantic to read values from ORM
    attributes, not just plain dicts.
    """
    id:         int
    user_id:    int
    is_active:  bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Job ────────────────────────────────────────────────────────

class JobOut(BaseModel):
    """
    Returned whenever a job is included in an API response.
    Optional fields exist because job boards don't always
    provide salary, job type, or date posted.
    """
    id:          int
    job_id:      str
    site:        str
    title:       Optional[str]
    company:     Optional[str]
    location:    Optional[str]
    is_remote:   Optional[bool]
    job_type:    Optional[str]
    salary_min:  Optional[Decimal]
    salary_max:  Optional[Decimal]
    currency:    Optional[str]
    job_url:     Optional[str]
    date_posted: Optional[date]
    scraped_at:  datetime
    model_config = ConfigDict(from_attributes=True)


# ── Scrape trigger ─────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    """
    Body payload for POST /jobs/scrape.
    Used when triggering a one-off scrape without a saved config.
    """
    search_term:    str
    location:       Optional[str] = None
    site_names:     str  = "linkedin,indeed,glassdoor"
    results_wanted: int  = 20
    is_remote:      Optional[bool] = None


class ScrapeResult(BaseModel):
    """
    What every scrape endpoint returns — a count of new jobs
    found and the actual job objects so the caller can use them
    immediately (e.g. the notifier formats them for Telegram).
    """
    new_jobs_found: int
    jobs:           list[JobOut]