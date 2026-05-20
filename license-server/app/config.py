import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    admin_password: str
    secret_key: str
    db_path: str
    gemini_api_key: str = ""

def load_settings() -> Settings:
    admin_password = os.environ.get("ADMIN_PASSWORD")
    secret_key = os.environ.get("SECRET_KEY")
    db_path = os.environ.get("DB_PATH", "licenses.db")
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD environment variable is required")
    if not secret_key or len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY environment variable must be at least 32 chars")
    return Settings(admin_password=admin_password, secret_key=secret_key,
                    db_path=db_path, gemini_api_key=gemini_api_key)
