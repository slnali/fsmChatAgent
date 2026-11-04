"""Runs the agent's SQL as fsm_agent_ro: read-only, time-boxed and capped at max_rows.

The database role is the safety boundary: it can only SELECT from the `data` schema.
"""

import datetime as dt
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

import psycopg


@dataclass(frozen=True)
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuleMetrics:
    matched_count: int
    labelled_count: int
    fraud_count: int
    fraud_rate: float | None


class RuleEvaluationError(Exception):
    pass


class ReadOnlyExecutor:
    def __init__(self, dsn: str, max_rows: int = 20) -> None:
        self._dsn = dsn
        self._max_rows = max_rows

    def run(self, sql: str) -> QueryResult:
        # Fetch one extra row to know whether the result was truncated.
        # The newline stops a trailing `--` comment from swallowing the closing bracket.
        capped = f"SELECT * FROM (\n{_strip_semicolons(sql)}\n) AS q LIMIT {self._max_rows + 1}"
        try:
            columns, rows = self._fetch(capped)
        except psycopg.Error as error:
            return QueryResult(error=_postgres_message(error))

        truncated = len(rows) > self._max_rows
        rows = rows[: self._max_rows]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)

    def evaluate_rule(self, where_clause: str) -> RuleMetrics:
        if not where_clause.strip():
            raise RuleEvaluationError("The WHERE clause is empty.")
        try:
            _, rows = self._fetch(rule_count_sql(where_clause))
        except psycopg.Error as error:
            raise RuleEvaluationError(_postgres_message(error)) from error

        matched, labelled, fraud = rows[0]
        return RuleMetrics(
            matched_count=matched,
            labelled_count=labelled,
            fraud_count=fraud,
            fraud_rate=round(fraud / labelled, 6) if labelled else None,
        )

    def _fetch(self, sql: str) -> tuple[list[str], list[list[Any]]]:
        with psycopg.connect(self._dsn) as conn:
            conn.read_only = True
            with conn.cursor() as cursor:
                cursor.execute(sql.encode())
                columns = [column.name for column in cursor.description or []]
                rows = [[_to_json_value(value) for value in row] for row in cursor.fetchall()]
        return columns, rows


def rule_count_sql(where_clause: str) -> str:
    """The SQL a rule's WHERE clause is evaluated in (newlines stop `--` comment tricks)."""
    return (
        "SELECT COUNT(*) AS matched_count,\n"
        "       COUNT(fl.transaction_id) AS labelled_count,\n"
        "       COUNT(*) FILTER (WHERE fl.is_fraud) AS fraud_count\n"
        "FROM data.transactions t\n"
        "LEFT JOIN data.fraud_labels fl ON fl.transaction_id = t.id::text\n"
        f"WHERE (\n{where_clause}\n)"
    )


def _strip_semicolons(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def _postgres_message(error: psycopg.Error) -> str:
    diag = error.diag
    return (diag.message_primary or str(error)).strip() + (
        f" (hint: {diag.message_hint})" if diag.message_hint else ""
    )


def _to_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    return value
