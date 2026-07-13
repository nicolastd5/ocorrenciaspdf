import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    admin_password: str
    secret_key: str
    db_path: str
    data_dir: str = "data"
    redis_url: str = "redis://localhost:6379/0"
    gemini_api_key: str = ""

def load_settings() -> Settings:
    admin_password = os.environ.get("ADMIN_PASSWORD")
    secret_key = os.environ.get("SECRET_KEY")
    db_path = os.environ.get("DB_PATH", "licenses.db")
    data_dir = os.environ.get("DATA_DIR", "data")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD environment variable is required")
    if not secret_key or len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY environment variable must be at least 32 chars")
    return Settings(admin_password=admin_password, secret_key=secret_key,
                    db_path=db_path, data_dir=data_dir, redis_url=redis_url,
                    gemini_api_key=gemini_api_key)
