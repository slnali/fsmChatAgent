"""Prepares the docker compose Postgres: migrate, then load the data once.

uv run python scripts/setup_local_db.py      (what `task db` runs)
"""

import time

import psycopg

from fsm_ai.config import get_settings
from fsm_ai.migrations.runner import apply_migrations
from scripts.build_context_profile import PROFILE_FILE
from scripts.build_context_profile import main as build_profile
from scripts.load_data import load, unpack


def wait_for_database(dsn: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            psycopg.connect(dsn, connect_timeout=3).close()
            return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


def main() -> None:
    settings = get_settings()
    wait_for_database(settings.owner_database_url)

    applied = apply_migrations(settings.owner_database_url, settings.migration_variables())
    print(f"Migrations applied: {', '.join(applied) or 'none pending'}")

    with psycopg.connect(settings.owner_database_url) as conn:
        row = conn.execute("SELECT EXISTS (SELECT 1 FROM data.transactions)").fetchone()
    if row and row[0]:
        print("Data already loaded.")
    else:
        print("Loading data (first run only, about a minute)...")
        load(settings.owner_database_url, unpack(settings.data_db_file))

    if not PROFILE_FILE.exists():
        build_profile()


if __name__ == "__main__":
    main()
