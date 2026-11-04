"""Loads the provided SQLite data.db into the Postgres `data` schema (as the owner user).

uv run python scripts/load_data.py
"""

import gzip
import shutil
import sqlite3
import time
from pathlib import Path

import psycopg

from fsm_ai.config import SOLUTION_ROOT, get_settings

CACHE_DIR = SOLUTION_ROOT / "data" / ".cache"

# Parents before children, so foreign keys hold while loading.
TABLE_ORDER = [
    "users",
    "mcc_codes",
    "merchants",
    "merchant_locations",
    "cards",
    "fraud_labels",
    "transactions",
]
BOOLEAN_COLUMNS = {"cards": {"has_chip", "card_on_dark_web"}, "fraud_labels": {"is_fraud"}}


def unpack(data_file: Path) -> Path:
    """data.db ships gzipped (GitHub's 100 MB limit); unpack it once into data/.cache/."""
    if data_file.suffix != ".gz":
        return data_file
    target = CACHE_DIR / data_file.stem
    if not target.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Unpacking {data_file.name} -> {target}")
        with gzip.open(data_file, "rb") as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)
    return target


def load(owner_dsn: str, sqlite_file: Path) -> None:
    source = sqlite3.connect(f"file:{sqlite_file}?mode=ro", uri=True)
    try:
        with psycopg.connect(owner_dsn) as target:
            for table in TABLE_ORDER:
                started = time.monotonic()
                count = _copy_table(source, target, table)
                print(f"  data.{table}: {count:,} rows ({time.monotonic() - started:.1f}s)")
            target.commit()
        with psycopg.connect(owner_dsn, autocommit=True) as conn:
            conn.execute("ANALYZE")
    finally:
        source.close()


def _copy_table(source: sqlite3.Connection, target: psycopg.Connection, table: str) -> int:
    columns = [row[1] for row in source.execute(f"PRAGMA table_info({table})")]
    booleans = [
        index for index, name in enumerate(columns) if name in BOOLEAN_COLUMNS.get(table, set())
    ]
    column_list = ", ".join(columns)
    count = 0
    with target.cursor() as cursor:
        copy_sql = f"COPY data.{table} ({column_list}) FROM STDIN"
        with cursor.copy(copy_sql.encode()) as copy:
            for row in source.execute(f"SELECT {column_list} FROM {table}"):
                values = list(row)
                for index in booleans:
                    if values[index] is not None:
                        values[index] = bool(values[index])
                copy.write_row(values)
                count += 1
    return count


def main() -> None:
    settings = get_settings()
    load(settings.owner_database_url, unpack(settings.data_db_file))


if __name__ == "__main__":
    main()
