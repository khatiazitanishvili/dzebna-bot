import asyncio
import logging
from fastapi import FastAPI
from app.db import engine, Base
import app.models
from app.routers import jobs
from app.services.bot import build_bot_app
from app.services.scheduler import start_scheduler
from app.config import settings

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title       = "Job Notifier API",
    description = "Scrapes job boards and notifies via Telegram.",
    version     = "1.0.0",
)

# Module-level bot app — built once, reused by scheduler and handlers
bot_app = build_bot_app(settings.telegram_bot_token)


@app.on_event("startup")
async def startup() -> None:
    # 1. Ensure all DB tables exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    # 2. Start the Telegram bot polling loop as a background task.
    #    initialize() sets up the bot session.
    #    updater.start_polling() begins long-polling Telegram for messages.
    #    Running as a task means it doesn't block FastAPI from starting.
    await bot_app.initialize()
    await bot_app.updater.start_polling()
    await bot_app.start()
    asyncio.create_task(_keep_bot_running())
    logger.info("Telegram bot polling started")

    # 3. Start the APScheduler with the bot instance so it can
    #    send messages when the notify cycle fires
    start_scheduler(bot_app.bot)
    logger.info("Scheduler started")


@app.on_event("shutdown")
async def shutdown() -> None:
    # Gracefully stop the bot and scheduler when the container stops
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Bot stopped gracefully")


async def _keep_bot_running() -> None:
    """
    Keeps the bot polling task alive for the lifetime of the app.
    Sleeps in 60s intervals indefinitely — exits cleanly when the
    app shuts down and the task is cancelled.
    """
    while True:
        await asyncio.sleep(60)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(jobs.router)