"""
Standalone script to test the scraper without starting the full app.
Run from the project root inside the app container:
    docker compose exec app python -m app.services.run_scrape
"""
import logging
from app.db import SessionLocal
from app.models import User, SearchConfig
from app.services.scraper import run_scrape_for_user
from app.config import settings

logging.basicConfig(level=logging.INFO)

def main():
    db = SessionLocal()

    # Create a test user if one doesn't exist
    user = db.query(User).filter_by(chat_id=999999).first()
    if not user:
        user = User(chat_id=999999, username="test_user")
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create a test search config if one doesn't exist
    config = db.query(SearchConfig).filter_by(user_id=user.id).first()
    if not config:
        config = SearchConfig(
            user_id        = user.id,
            search_term    = settings.default_search_term,
            location       = settings.default_location,
            results_wanted = settings.default_results_wanted,
            site_names     = "linkedin,indeed",
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    new_jobs = run_scrape_for_user(db, config)

    print(f"\n--- Scrape complete: {len(new_jobs)} new jobs ---")
    for job in new_jobs[:5]:
        print(f"  [{job.site}] {job.title} @ {job.company} — {job.location}")
        print(f"  {job.job_url}\n")

    db.close()

if __name__ == "__main__":
    main()