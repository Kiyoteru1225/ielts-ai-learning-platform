import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ielts.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")


settings = Settings()
