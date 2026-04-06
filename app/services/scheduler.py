import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User, SearchConfig, Notification
from app.services.scraper import run_scrape_for_user
from app.services.notifier import send_job_digest
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level scheduler instance — started once during app startup
scheduler = AsyncIOScheduler()


def start_scheduler(bot: Bot) -> None:
    """
    Registers the notify job and starts the scheduler.
    Called once from main.py during FastAPI startup.
    bot is passed in so the scheduler can send Telegram messages.
    """
    scheduler.add_job(
        func        = _run_notify_cycle,
       # trigger     = IntervalTrigger(hours=settings.notify_interval_hours),
        trigger     = IntervalTrigger(minutes=settings.notify_interval_minutes),
        args        = [bot],
        id          = "notify_cycle",
        name        = "Scrape and notify all active users",
        replace_existing = True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started — notify cycle every "
        f"{settings.notify_interval_minutes} minute(s)"
    )


async def _run_notify_cycle(bot: Bot) -> None:
    """
    The core scheduled task:
    1. Fetch all active users
    2. For each user, scrape their active search configs
    3. Filter out jobs already sent to that user
    4. Send a digest if there are new jobs
    """
    logger.info("Scheduler: starting notify cycle")
    db = SessionLocal()

    try:
        active_users = db.query(User).filter_by(is_active=True).all()
        logger.info(f"Scheduler: processing {len(active_users)} active users")

        for user in active_users:
            await _process_user(bot, user, db)

    except Exception as e:
        logger.error(f"Scheduler: notify cycle failed: {e}")
    finally:
        # Always close the session — even if something goes wrong
        db.close()

    logger.info("Scheduler: notify cycle complete")


async def _process_user(bot: Bot, user: User, db: Session) -> None:
    configs = (
        db.query(SearchConfig)
        .filter_by(user_id=user.id, is_active=True)
        .all()
    )
    if not configs:
        return

    # Step 1: run the scraper to pull in any brand new jobs
    for config in configs:
        run_scrape_for_user(db, config)

    # Step 2: find ALL jobs in the DB not yet sent to this user
    # This catches jobs scraped earlier that were never sent to them
    from app.models import Job, Notification
    already_sent_ids = {
        n.job_id for n in
        db.query(Notification).filter_by(user_id=user.id).all()
    }

    unsent_jobs = (
        db.query(Job)
        .filter(Job.id.notin_(already_sent_ids))
        .order_by(Job.scraped_at.desc())
        .limit(50)
        .all()
    )

    if unsent_jobs:
        await send_job_digest(bot, user, unsent_jobs, db)
    else:
        logger.info(f"No new jobs for user {user.chat_id} — skipping")


async def trigger_now_for_user(bot: Bot, user: User, db: Session) -> int:
    """
    Called by the Telegram /trigger command handler.
    Runs the same logic as the scheduled cycle but for one user only,
    immediately. Returns the count of new jobs sent.
    """
    await _process_user(bot, user, db)

    # Count what was just sent by checking recent notifications
    from datetime import datetime, timedelta
    recent_cutoff = datetime.utcnow() - timedelta(minutes=1)
    recent_count  = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.sent_at >= recent_cutoff,
        )
        .count()
    )
    return recent_count