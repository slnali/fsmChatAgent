"""Session-scoped throwaway Postgres (testcontainers) migrated exactly like prod, plus seed data."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from testcontainers.community.postgres import PostgresContainer

from fsm_ai.agent.runner import LangChainAgentRunner
from fsm_ai.agent.tools import AgentTools
from fsm_ai.api.app import create_app
from fsm_ai.context.system_prompt import build_system_prompt
from fsm_ai.data_access.readonly_executor import ReadOnlyExecutor
from fsm_ai.migrations.runner import apply_migrations
from fsm_ai.persistence.chats import ChatRepo
from fsm_ai.persistence.database import AppDatabase
from fsm_ai.persistence.messages import MessageRepo
from fsm_ai.persistence.rules import RuleRepo
from fsm_ai.services import Services
from tests.builders import ScriptedChatModel

SEED_FILE = Path(__file__).parent / "fixtures" / "seed.sql"
ROLE_PASSWORDS = {"fsm_agent_ro_password": "agent_ro_test", "fsm_app_password": "app_test"}
TEST_MAX_ROWS = 5


@dataclass(frozen=True)
class DatabaseUrls:
    owner: str
    agent_ro: str
    app: str


@pytest.fixture(scope="session")
def database_urls() -> Iterator[DatabaseUrls]:
    with PostgresContainer(
        "postgres:17", username="owner", password="owner", dbname="fsm", driver=None
    ) as pg:
        host, port = pg.get_container_host_ip(), pg.get_exposed_port(5432)

        def url(user: str, password: str) -> str:
            return f"postgresql://{user}:{password}@{host}:{port}/fsm"

        urls = DatabaseUrls(
            owner=url("owner", "owner"),
            agent_ro=url("fsm_agent_ro", ROLE_PASSWORDS["fsm_agent_ro_password"]),
            app=url("fsm_app", ROLE_PASSWORDS["fsm_app_password"]),
        )
        apply_migrations(urls.owner, ROLE_PASSWORDS)
        with psycopg.connect(urls.owner) as conn:
            conn.execute(SEED_FILE.read_bytes())
        yield urls


@pytest.fixture
def executor(database_urls: DatabaseUrls) -> ReadOnlyExecutor:
    return ReadOnlyExecutor(database_urls.agent_ro, max_rows=TEST_MAX_ROWS)


@pytest.fixture
def make_client(
    database_urls: DatabaseUrls, executor: ReadOnlyExecutor
) -> Callable[[list[AIMessage]], tuple[TestClient, ScriptedChatModel]]:
    """Builds the real app wired to the test database and a scripted model."""

    def build(replies: list[AIMessage]) -> tuple[TestClient, ScriptedChatModel]:
        model = ScriptedChatModel(replies=list(replies))
        app_db = AppDatabase(database_urls.app)
        services = Services(
            chats=ChatRepo(app_db),
            messages=MessageRepo(app_db),
            rules=RuleRepo(app_db),
            executor=executor,
            agent=LangChainAgentRunner(
                llm=model,
                tools=AgentTools(executor),
                system_prompt=build_system_prompt(TEST_MAX_ROWS),
                model_name="scripted",
            ),
        )
        return TestClient(create_app(services)), model

    return build
