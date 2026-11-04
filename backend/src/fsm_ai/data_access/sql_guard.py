"""Deterministic first line of defence: a single read-only SELECT over the `data` schema.

The database role (fsm_agent_ro) is the real boundary. The guard rejects bad SQL early,
with a clear reason the agent can act on.
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ALLOWED_SCHEMA = "data"

FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Command,  # SET ROLE, VACUUM, CALL, SHOW, EXPLAIN ... fall back to Command
    exp.Set,
    exp.Into,  # SELECT ... INTO creates a table
    exp.Lock,  # FOR UPDATE / FOR SHARE
    exp.Grant,
    exp.Revoke,
    exp.Transaction,
    exp.Commit,
)

FORBIDDEN_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink")
FORBIDDEN_FUNCTIONS = {
    "set_config",
    "current_setting",
    "query_to_xml",
    "query_to_xml_and_xmlschema",
    "nextval",
    "setval",
}


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str = ""


def _reject(reason: str) -> GuardResult:
    return GuardResult(ok=False, reason=reason)


class SqlGuard:
    def check(self, sql: str) -> GuardResult:
        try:
            statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
        except SqlglotError as error:
            return _reject(f"Could not parse SQL: {error}")

        if len(statements) != 1:
            return _reject("Exactly one SQL statement is allowed.")

        root = statements[0]
        if not isinstance(root, exp.Select | exp.SetOperation):
            return _reject("Only SELECT queries are allowed.")

        for node in root.walk():
            if isinstance(node, FORBIDDEN_NODES):
                return _reject(f"{type(node).__name__} is not allowed; queries must be read-only.")
            if isinstance(node, exp.Func) and _is_forbidden_function(node):
                return _reject(f"Function '{_function_name(node)}' is not allowed.")

        return self._check_tables(root)

    def check_where_clause(self, where_clause: str) -> GuardResult:
        """A rule is a WHERE clause on data.transactions (alias t)."""
        if not where_clause.strip():
            return _reject("The WHERE clause is empty.")
        result = self.check(rule_count_sql(where_clause))
        if not result.ok:
            return result
        root = sqlglot.parse_one(rule_count_sql(where_clause), read="postgres")
        if not isinstance(root, exp.Select):
            return _reject("The WHERE clause must be a single boolean condition.")
        return result

    @staticmethod
    def _check_tables(root: exp.Expression) -> GuardResult:
        cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
        for table in root.find_all(exp.Table):
            if isinstance(table.this, exp.Func):  # e.g. generate_series(...)
                continue
            schema = table.db.lower()
            if not schema and table.name.lower() in cte_names:
                continue
            if schema != ALLOWED_SCHEMA:
                qualified = f"{schema}.{table.name}" if schema else table.name
                return _reject(
                    f"Table '{qualified}' is not allowed; only '{ALLOWED_SCHEMA}.*' tables "
                    "can be queried (always schema-qualify them)."
                )
        return GuardResult(ok=True)


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


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return node.name.lower()
    return node.sql_name().lower()


def _is_forbidden_function(node: exp.Func) -> bool:
    name = _function_name(node)
    return name in FORBIDDEN_FUNCTIONS or name.startswith(FORBIDDEN_FUNCTION_PREFIXES)
