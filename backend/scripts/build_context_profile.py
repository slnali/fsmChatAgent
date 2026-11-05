"""Layer 3 context: profiles the `data` tables into context/profile.json.

It reads the statistics Postgres already keeps (`pg_stats`, refreshed by ANALYZE and
autovacuum), so it never scans the data and works the same on a large database. The figures
come from ANALYZE's sample, so they are approximate. It runs as the read-only agent role:
pg_stats only shows tables the role can read.

uv run python scripts/build_context_profile.py
"""

import json
from typing import Any

import psycopg

from fsm_ai.config import BACKEND_ROOT, get_settings

PROFILE_FILE = BACKEND_ROOT / "context" / "profile.json"
MAX_LISTED_VALUES = 20  # only list values for low-cardinality columns (keeps out names, PII)

TABLES_SQL = """
SELECT c.relname, c.reltuples::bigint
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'data' AND c.relkind = 'r'
ORDER BY c.relname
"""

COLUMNS_SQL = """
SELECT col.column_name,
       col.data_type,
       s.null_frac,
       s.n_distinct,
       array_to_json(s.most_common_vals::text::text[]),
       array_to_json(s.most_common_freqs),
       array_to_json(s.histogram_bounds::text::text[])
FROM information_schema.columns col
LEFT JOIN pg_stats s
       ON s.schemaname = col.table_schema
      AND s.tablename = col.table_name
      AND s.attname = col.column_name
WHERE col.table_schema = 'data' AND col.table_name = %s
ORDER BY col.ordinal_position
"""


def build_profile(dsn: str) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn:
        tables = conn.execute(TABLES_SQL).fetchall()
        return {
            "source": "pg_stats (ANALYZE sample): counts and percentages are approximate",
            "tables": {
                table: {
                    "row_count": row_count,
                    "columns": {
                        row[0]: _column_profile(row, row_count)
                        for row in conn.execute(COLUMNS_SQL, (table,)).fetchall()
                    },
                }
                for table, row_count in tables
            },
        }


def _column_profile(row: tuple[Any, ...], row_count: int) -> dict[str, Any]:
    _, data_type, null_frac, n_distinct, values, freqs, bounds = row
    profile: dict[str, Any] = {"type": data_type}
    if null_frac is None:  # not analysed yet
        return profile

    profile["null_pct"] = round(100 * null_frac, 2)
    # A negative n_distinct is a fraction of the rows (-1 means every value is unique).
    distinct = round(-n_distinct * row_count) if n_distinct < 0 else round(n_distinct)
    profile["distinct"] = distinct
    if values and distinct <= MAX_LISTED_VALUES:
        profile["values_pct"] = {
            _readable(value, data_type): round(100 * freq, 3)
            for value, freq in zip(values, freqs, strict=True)
        }
    elif bounds:
        profile["range"] = [bounds[0], bounds[-1]]
    return profile


def _readable(value: str, data_type: str) -> str:
    if data_type == "boolean":
        return {"t": "true", "f": "false"}.get(value, value)
    return value


def main() -> None:
    profile = build_profile(get_settings().agent_ro_database_url)
    PROFILE_FILE.write_text(json.dumps(profile, indent=2) + "\n")
    print(f"Wrote {PROFILE_FILE}")


if __name__ == "__main__":
    main()
