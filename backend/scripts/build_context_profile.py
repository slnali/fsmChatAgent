"""Layer 3 context: profiles the `data` tables into context/profile.json.

uv run python scripts/build_context_profile.py
"""

import json
from typing import Any

import psycopg
from psycopg import sql

from fsm_ai.config import BACKEND_ROOT, get_settings

PROFILE_FILE = BACKEND_ROOT / "context" / "profile.json"
MAX_DISTINCT_VALUES = 20
RANGE_TYPES = {
    "integer",
    "bigint",
    "real",
    "double precision",
    "numeric",
    "date",
    "timestamp without time zone",
}


def build_profile(dsn: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = 'data' ORDER BY table_name"
            )
        ]
        profile: dict[str, Any] = {"tables": {}}
        for table in tables:
            profile["tables"][table] = _profile_table(conn, table)
        profile["facts"] = _facts(conn)
    return profile


def _profile_table(conn: psycopg.Connection, table: str) -> dict[str, Any]:
    table_id = sql.Identifier("data", table)
    row_count = _scalar(conn, sql.SQL("SELECT COUNT(*) FROM {}").format(table_id))
    columns = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns"
        " WHERE table_schema = 'data' AND table_name = %s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    profiled: dict[str, Any] = {}
    for name, data_type in columns:
        stats: dict[str, Any] = {"type": data_type}
        column = sql.Identifier(name)
        nulls = _scalar(
            conn, sql.SQL("SELECT COUNT(*) FROM {} WHERE {} IS NULL").format(table_id, column)
        )
        stats["null_pct"] = round(100 * nulls / row_count, 2) if row_count else 0
        distinct = _scalar(
            conn, sql.SQL("SELECT COUNT(DISTINCT {}) FROM {}").format(column, table_id)
        )
        stats["distinct"] = distinct
        if data_type in RANGE_TYPES:
            low, high = conn.execute(
                sql.SQL("SELECT MIN({0}), MAX({0}) FROM {1}").format(column, table_id)
            ).fetchone() or (None, None)
            stats["min"], stats["max"] = str(low), str(high)
        if distinct <= MAX_DISTINCT_VALUES:
            stats["values"] = {
                str(value): count
                for value, count in conn.execute(
                    sql.SQL("SELECT {}, COUNT(*) FROM {} GROUP BY 1 ORDER BY 2 DESC").format(
                        column, table_id
                    )
                )
            }
        profiled[name] = stats
    return {"row_count": row_count, "columns": profiled}


def _facts(conn: psycopg.Connection) -> dict[str, Any]:
    labelled, fraud = conn.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE is_fraud) FROM data.fraud_labels"
    ).fetchone() or (0, 0)
    return {
        "labelled_transactions": labelled,
        "fraud_transactions": fraud,
        "base_fraud_rate_pct": round(100 * fraud / labelled, 4) if labelled else None,
    }


def _scalar(conn: psycopg.Connection, query: sql.Composed) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0]) if row else 0


def main() -> None:
    profile = build_profile(get_settings().owner_database_url)
    PROFILE_FILE.write_text(json.dumps(profile, indent=2) + "\n")
    print(f"Wrote {PROFILE_FILE}")


if __name__ == "__main__":
    main()
