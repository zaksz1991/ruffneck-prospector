from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""  # service role for backend

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # AI
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"  # or whatever is free currently

    # Scraping
    apify_token: Optional[str] = None
    # Reddit (PRAW) - free if you create an app
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "RuffNeckProspector/1.0 by u/yourusername"

    # Email (Resend free tier)
    resend_api_key: Optional[str] = None
    from_email: str = "outreach@yourdomain.com"

    # App
    environment: str = "development"
    max_scrape_results: int = 100  # free-tier safety
    rate_limit_per_minute: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
