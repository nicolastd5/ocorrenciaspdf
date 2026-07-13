"""Limpeza de jobs expirados — agendar no cron: diário.

Ex.: 15 3 * * * cd /opt/ocorrencias && .venv/bin/python cleanup.py
"""
from app.config import load_settings
from app.jobs import cleanup_expired

if __name__ == "__main__":
    s = load_settings()
    n = cleanup_expired(s.db_path, s.data_dir)
    print(f"{n} job(s) expirados removidos")
