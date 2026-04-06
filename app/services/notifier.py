import logging
from telegram import Bot
from telegram.error import TelegramError
from app.models import Job, User, Notification
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_JOBS_PER_MESSAGE = 10  # Telegram has a 4096 char message limit


async def send_job_digest(
    bot: Bot,
    user: User,
    new_jobs: list[Job],
    db: Session,
) -> None:
    """
    Formats new_jobs into a readable Telegram message and sends it
    to the user. Also records each sent job in the notifications
    table so the same job is never sent twice.
    """
    if not new_jobs:
        return

    # Trim to max jobs per message to avoid hitting Telegram's
    # 4096 character limit
    jobs_to_send = new_jobs[:MAX_JOBS_PER_MESSAGE]
    remaining    = len(new_jobs) - len(jobs_to_send)

    message = _format_digest(jobs_to_send, remaining)

    try:
        await bot.send_message(
            chat_id    = user.chat_id,
            text       = message,
            parse_mode = "HTML",
            # disable_web_page_preview stops Telegram from expanding
            # every job link into a giant preview card
            disable_web_page_preview = True,
        )

        # Record every sent job so the scheduler never sends it again
        for job in jobs_to_send:
            _record_notification(db, user.id, job.id)

        logger.info(f"Sent {len(jobs_to_send)} jobs to user {user.chat_id}")

    except TelegramError as e:
        logger.error(f"Failed to send message to {user.chat_id}: {e}")


def _format_digest(jobs: list[Job], remaining: int) -> str:
    """
    Builds the HTML message string.
    Example output:

    <b>3 new jobs · Python developer, Berlin</b>
    ─────────────────────────────
    1. <b>Senior Python Engineer</b>
       Zalando · Berlin · €80k–110k · Remote
       <a href="...">View on LinkedIn</a>
    ...
    """
    count   = len(jobs)
    header  = f"<b>{count} new job{'s' if count > 1 else ''} found</b>\n"
    divider = "─" * 30 + "\n"

    lines = [header, divider]

    for i, job in enumerate(jobs, start=1):
        title   = job.title   or "Untitled"
        company = job.company or "Unknown company"
        site    = job.site.capitalize()

        # Build location + remote string
        location_parts = []
        if job.location:
            location_parts.append(job.location)
        if job.is_remote:
            location_parts.append("Remote")
        location_str = " · ".join(location_parts) if location_parts else "Location N/A"

        # Build salary string only if we have data
        salary_str = _format_salary(job)

        # Combine meta line: company · location · salary
        meta_parts = [company, location_str]
        if salary_str:
            meta_parts.append(salary_str)
        meta = " · ".join(meta_parts)

        # Job URL as a clickable link labelled by source
        link = f'<a href="{job.job_url}">View on {site}</a>' if job.job_url else "No link available"

        lines.append(f"{i}. <b>{title}</b>\n   {meta}\n   {link}\n")

    if remaining > 0:
        lines.append(f"\n<i>+{remaining} more jobs not shown</i>\n")

    lines.append(divider)
    lines.append("<i>Send /trigger to check for new jobs now</i>")

    return "\n".join(lines)


def _format_salary(job: Job) -> str:
    """Returns a formatted salary string or empty string if no data."""
    if not job.salary_min and not job.salary_max:
        return ""
    currency = job.currency or ""
    if job.salary_min and job.salary_max:
        return f"{currency}{int(job.salary_min):,}–{int(job.salary_max):,}"
    if job.salary_min:
        return f"From {currency}{int(job.salary_min):,}"
    if job.salary_max:
        return f"Up to {currency}{int(job.salary_max):,}"
    return ""


def _record_notification(db: Session, user_id: int, job_id: int) -> None:
    """
    Inserts a row into the notifications table.
    The UNIQUE constraint on (user_id, job_id) means if this is
    called twice for the same pair it silently does nothing.
    """
    from app.models import Notification
    from sqlalchemy.exc import IntegrityError

    notification = Notification(user_id=user_id, job_id=job_id)
    try:
        db.add(notification)
        db.commit()
    except IntegrityError:
        # Already sent — unique constraint fired, safe to ignore
        db.rollback()