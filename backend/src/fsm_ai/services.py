"""Composition root: builds the real dependencies from settings."""

from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from fsm_ai.agent.runner import AgentRunner, LangChainAgentRunner
from fsm_ai.agent.tools import AgentTools
from fsm_ai.config import Settings
from fsm_ai.context.system_prompt import cached_system_prompt
from fsm_ai.data_access.readonly_executor import ReadOnlyExecutor
from fsm_ai.persistence.chats import ChatRepo
from fsm_ai.persistence.database import AppDatabase
from fsm_ai.persistence.messages import MessageRepo
from fsm_ai.persistence.rules import RuleRepo


@dataclass(frozen=True)
class Services:
    chats: ChatRepo
    messages: MessageRepo
    rules: RuleRepo
    executor: ReadOnlyExecutor
    agent: AgentRunner


def build_executor(settings: Settings) -> ReadOnlyExecutor:
    return ReadOnlyExecutor(settings.agent_ro_database_url, settings.max_result_rows)


def build_agent(settings: Settings, executor: ReadOnlyExecutor) -> LangChainAgentRunner:
    # Sonnet 5.5 only accepts the default temperature, so it is not set here; grounding
    # (context layers 1-3) and the evals do the work temperature=0 used to.
    llm = ChatAnthropic(
        model=settings.agent_model,
        max_tokens=4096,
        api_key=SecretStr(settings.anthropic_api_key),
    )
    return LangChainAgentRunner(
        llm=llm,
        tools=AgentTools(executor),
        system_prompt=cached_system_prompt(settings.max_result_rows),
        model_name=settings.agent_model,
        max_steps=settings.max_agent_steps,
    )


def build_services(settings: Settings) -> Services:
    app_db = AppDatabase(settings.app_database_url)
    executor = build_executor(settings)
    return Services(
        chats=ChatRepo(app_db),
        messages=MessageRepo(app_db),
        rules=RuleRepo(app_db),
        executor=executor,
        agent=build_agent(settings, executor),
    )
