import logging
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User, SearchConfig, Notification
from app.services.scheduler import trigger_now_for_user
from app.config import settings

logger = logging.getLogger(__name__)


# ── Helper: get or create user ─────────────────────────────────

def _get_or_create_user(db: Session, chat_id: int, username: str) -> User:
    """
    Returns the existing user or creates a new one with a default
    search config seeded from .env settings.
    This is the only place users are created in the whole app.
    """
    user = db.query(User).filter_by(chat_id=chat_id).first()
    if user:
        return user

    # New user — create them
    user = User(
        chat_id  = chat_id,
        username = username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Seed their first search config from .env defaults
    config = SearchConfig(
        user_id        = user.id,
        search_term    = settings.default_search_term,
        location       = settings.default_location,
        results_wanted = settings.default_results_wanted,
        site_names     = "linkedin,indeed,glassdoor",
    )
    db.add(config)
    db.commit()

    logger.info(f"New user registered: {username} (chat_id={chat_id})")
    return user


# ── Command handlers ───────────────────────────────────────────

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start — registers the user and confirms their search config.
    Safe to call multiple times — won't create duplicate users.
    """
    chat_id  = update.effective_chat.id
    username = update.effective_chat.username or "unknown"

    db   = SessionLocal()
    user = _get_or_create_user(db, chat_id, username)
    db.close()

    # Check if this was a fresh registration or an existing user
    is_new = user.created_at == user.updated_at

    if is_new:
        await update.message.reply_text(
            f"You're all set!\n\n"
            f"I'll search for <b>{settings.default_search_term}</b> "
            f"in <b>{settings.default_location}</b> every "
            f"<b>{settings.notify_interval_minutes} minute(s)</b>.\n\n"
            f"Send /trigger to get your first batch right now.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "You're already registered and active.\n"
            "Send /status to see your current config.",
        )


async def handle_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /trigger — immediately runs a scrape for this user and sends results.
    This is the on-demand alternative to waiting for the scheduler.
    """
    chat_id  = update.effective_chat.id
    username = update.effective_chat.username or "unknown"

    await update.message.reply_text(
        "Scraping now, this takes about 20 seconds..."
    )

    db   = SessionLocal()
    user = _get_or_create_user(db, chat_id, username)

    new_count = await trigger_now_for_user(
        bot  = context.bot,
        user = user,
        db   = db,
    )
    db.close()

    if new_count == 0:
        await update.message.reply_text(
            "No new jobs since your last check.\n"
            "I'll keep watching and notify you when something appears."
        )


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /status — shows the user's current config and stats.
    """
    chat_id = update.effective_chat.id
    db      = SessionLocal()

    user = db.query(User).filter_by(chat_id=chat_id).first()
    if not user:
        await update.message.reply_text(
            "You're not registered yet. Send /start to begin."
        )
        db.close()
        return

    configs = db.query(SearchConfig).filter_by(user_id=user.id, is_active=True).all()

    total_jobs_stored = db.query(Notification).filter_by(user_id=user.id).count()

    last_notification = (
        db.query(Notification)
        .filter_by(user_id=user.id)
        .order_by(Notification.sent_at.desc())
        .first()
    )

    db.close()

    config_lines = "\n".join(
        f"  • <b>{c.search_term}</b> in {c.location or 'any location'} "
        f"({'remote' if c.is_remote else 'all types'})"
        for c in configs
    ) or "  No active configs"

    last_notif_str = (
        last_notification.sent_at.strftime("%Y-%m-%d %H:%M")
        if last_notification else "Never"
    )

    await update.message.reply_text(
        f"<b>Your status</b>\n\n"
        f"Active searches:\n{config_lines}\n\n"
        f"Notification interval: every <b>{settings.notify_interval_hours}h</b>\n"
        f"Jobs sent so far: <b>{total_jobs_stored}</b>\n"
        f"Last notification: <b>{last_notif_str}</b>",
        parse_mode="HTML",
    )


async def handle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /pause — stops notifications without deleting the user's config.
    The scheduler checks is_active before processing each user.
    """
    chat_id = update.effective_chat.id
    db      = SessionLocal()

    user = db.query(User).filter_by(chat_id=chat_id).first()
    if not user:
        await update.message.reply_text("Send /start to register first.")
        db.close()
        return

    user.is_active = False
    db.commit()
    db.close()

    await update.message.reply_text(
        "Notifications paused. Send /resume to start again."
    )


async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /resume — re-enables notifications after a /pause.
    """
    chat_id = update.effective_chat.id
    db      = SessionLocal()

    user = db.query(User).filter_by(chat_id=chat_id).first()
    if not user:
        await update.message.reply_text("Send /start to register first.")
        db.close()
        return

    user.is_active = True
    db.commit()
    db.close()

    await update.message.reply_text(
        f"You're back! Next automatic check in "
        f"{settings.notify_interval_hours}h, "
        f"or send /trigger to check right now."
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /help — lists all available commands.
    """
    await update.message.reply_text(
        "<b>Available commands</b>\n\n"
        "/start — register and set up notifications\n"
        "/trigger — check for new jobs right now\n"
        "/status — see your config and stats\n"
        "/pause — stop notifications temporarily\n"
        "/resume — resume notifications\n"
        "/help — show this message",
        parse_mode="HTML",
    )


# ── Application builder ────────────────────────────────────────

def build_bot_app(token: str) -> Application:
    """
    Builds and returns the configured telegram Application object.
    Called once from main.py during FastAPI startup.
    Registers all command handlers.
    """
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",   handle_start))
    app.add_handler(CommandHandler("trigger", handle_trigger))
    app.add_handler(CommandHandler("status",  handle_status))
    app.add_handler(CommandHandler("pause",   handle_pause))
    app.add_handler(CommandHandler("resume",  handle_resume))
    app.add_handler(CommandHandler("help",    handle_help))

    return app