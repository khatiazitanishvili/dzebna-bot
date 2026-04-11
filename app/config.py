from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    default_search_term: str = "full-stack engineer"
    default_location: str = "Berlin, Germany"
    default_results_wanted: int = 20
    #notify_interval_hours: int = 6
    notify_interval_minutes: int = 1

    class Config:
        env_file = ".env"

settings = Settings()