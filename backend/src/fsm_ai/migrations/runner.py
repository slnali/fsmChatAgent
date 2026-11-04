"""Applies backend/migrations/NNN_*.sql in order, once each, as the owner (DB admin) user.

The same runner and files are used by tests, local runs and prod.
"""

import re
from pathlib import Path

import psycopg

from fsm_ai.config import BACKEND_ROOT

MIGRATIONS_DIR = BACKEND_ROOT / "migrations"
_VARIABLE = re.compile(r":'(\w+)'")


def substitute_variables(sql: str, variables: dict[str, str]) -> str:
    """Replaces psql-style :'name' variables with quoted literals."""

    def quote(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise KeyError(f"Migration variable '{name}' was not provided")
        return "'" + variables[name].replace("'", "''") + "'"

    return _VARIABLE.sub(quote, sql)


def apply_migrations(
    owner_dsn: str, variables: dict[str, str], migrations_dir: Path = MIGRATIONS_DIR
) -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(owner_dsn, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.schema_migrations ("
            " version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        already_applied = {
            row[0] for row in conn.execute("SELECT version FROM public.schema_migrations")
        }
        for path in sorted(migrations_dir.glob("*.sql")):
            if path.name in already_applied:
                continue
            with conn.transaction():
                conn.execute(substitute_variables(path.read_text(), variables).encode())
                conn.execute(
                    "INSERT INTO public.schema_migrations (version) VALUES (%s)", (path.name,)
                )
            applied_now.append(path.name)
    return applied_now
