"""The database is the real boundary: prove each role can only do its job."""

import psycopg
import pytest

from tests.conftest import DatabaseUrls


def test_agent_role_can_read_data(database_urls: DatabaseUrls) -> None:
    with psycopg.connect(database_urls.agent_ro) as conn:
        assert conn.execute("SELECT COUNT(*) FROM data.transactions").fetchone() == (40,)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO data.mcc_codes (mcc, description) VALUES (1, 'x')",
        "UPDATE data.cards SET card_on_dark_web = TRUE",
        "DROP TABLE data.transactions",
    ],
)
def test_agent_role_cannot_write_data(database_urls: DatabaseUrls, sql: str) -> None:
    with psycopg.connect(database_urls.agent_ro) as conn, pytest.raises(psycopg.Error):
        conn.execute(sql.encode())


def test_agent_role_cannot_escape_read_only_mode(database_urls: DatabaseUrls) -> None:
    with psycopg.connect(database_urls.agent_ro, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM data.cards")


def test_agent_role_cannot_read_chat_schema(database_urls: DatabaseUrls) -> None:
    with (
        psycopg.connect(database_urls.agent_ro) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute("SELECT * FROM fsm_chat.chat_messages")


def test_agent_role_has_statement_timeout(database_urls: DatabaseUrls) -> None:
    with psycopg.connect(database_urls.agent_ro) as conn:
        assert conn.execute("SHOW statement_timeout").fetchone() == ("15s",)
        assert conn.execute("SHOW default_transaction_read_only").fetchone() == ("on",)


def test_app_role_can_write_chats_but_cannot_read_data(database_urls: DatabaseUrls) -> None:
    with psycopg.connect(database_urls.app) as conn:
        conn.execute("INSERT INTO fsm_chat.chats (title) VALUES ('role test')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM data.transactions")
