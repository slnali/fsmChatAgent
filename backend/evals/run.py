"""Runs the golden set against the real agent and the local database, then writes the scorecard.

uv run python -m evals.run [--case <id>] [--concurrency N]
"""

import argparse
import asyncio
import datetime as dt
import sys
import time
from dataclasses import dataclass, field

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from evals.cases import AccuracyCase, GoldenSet, SafetyCase, load_golden_set
from evals.compare import Comparison, compare_results
from evals.judge import ClaudeGrader, Grade, Grader
from evals.safety import SqlAttempt, changed_tables, forbidden_attempts, is_refusal, snapshot
from evals.scorecard import (
    AccuracyResult,
    Report,
    SafetyResult,
    SqlStatus,
    render_markdown,
    write_report,
)
from fsm_ai.agent.events import StreamEvent, TurnFinished
from fsm_ai.agent.runner import AgentRunner
from fsm_ai.config import Settings, get_settings
from fsm_ai.context.system_prompt import PROMPT_VERSION
from fsm_ai.data_access.readonly_executor import QueryResult, ReadOnlyExecutor
from fsm_ai.services import build_agent, build_executor

# The agent sees at most max_result_rows; the eval re-runs its SQL with a higher cap.
EVAL_MAX_ROWS = 1000


@dataclass
class AgentTrace:
    """What one headless agent turn did."""

    answer: str = ""
    attempts: list[SqlAttempt] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    latency_s: float = 0.0
    tokens: int = 0

    @property
    def final_sql(self) -> tuple[str | None, SqlStatus]:
        """The last query that ran, which is the one the answer is based on."""
        for attempt in reversed(self.attempts):
            if attempt.error is None:
                return attempt.sql, "ran"
        if self.attempts:
            return self.attempts[-1].sql, "error"
        return None, "no_sql"


async def run_agent(agent: AgentRunner, question: str) -> AgentTrace:
    trace = AgentTrace()
    sql_by_call: dict[str, str] = {}
    started = time.monotonic()
    history = [{"role": "user", "content": {"text": question}}]
    async for event in agent.run_turn(history):
        if isinstance(event, TurnFinished):
            trace.tokens = sum(
                message.metadata.get("input_tokens", 0) + message.metadata.get("output_tokens", 0)
                for message in event.messages
                if message.role == "assistant"
            )
        else:
            _record(trace, sql_by_call, event)
    trace.latency_s = time.monotonic() - started
    return trace


def _record(trace: AgentTrace, sql_by_call: dict[str, str], event: StreamEvent) -> None:
    if event.name == "text_delta":
        trace.answer += event.data["text"]
    elif event.name == "tool_call":
        sql_by_call[event.data["id"]] = event.data["sql"]
    elif event.name == "tool_result":
        sql = sql_by_call.get(event.data["id"], "")
        trace.attempts.append(SqlAttempt(sql=sql, error=event.data.get("error")))
    elif event.name == "error":
        trace.errors.append(event.data["message"])


@dataclass(frozen=True)
class EvalContext:
    agent: AgentRunner
    executor: ReadOnlyExecutor
    grader: Grader
    agent_ro_dsn: str


async def run_accuracy_case(context: EvalContext, case: AccuracyCase) -> tuple[AccuracyResult, int]:
    trace = await run_agent(context.agent, case.question)
    agent_sql, status = trace.final_sql
    golden = await asyncio.to_thread(context.executor.run, case.golden_sql)
    generated: QueryResult | None = None
    if agent_sql is not None and status == "ran":
        generated = await asyncio.to_thread(context.executor.run, agent_sql)
        comparison = compare_results(golden, generated)
    else:
        comparison = Comparison("error", "The agent ran no successful SQL.")

    grade: Grade = await asyncio.to_thread(
        context.grader.grade,
        case.question,
        case.golden_sql,
        golden,
        agent_sql,
        generated,
        trace.answer,
        comparison,
    )
    result = AccuracyResult(
        case_id=case.id,
        level=case.level,
        question=case.question,
        answer=trace.answer.strip(),
        golden_sql=case.golden_sql.strip(),
        agent_sql=agent_sql.strip() if agent_sql else None,
        sql_status=status,
        comparison=comparison.outcome,
        comparison_detail=comparison.detail,
        score=grade.score,
        explanation=grade.explanation,
        latency_s=round(trace.latency_s, 1),
        tokens=trace.tokens,
        queries_run=len(trace.attempts),
    )
    _progress(f"accuracy {case.id}: {comparison.outcome}, grader {grade.score:.2f}")
    return result, grade.tokens


async def run_safety_case(context: EvalContext, case: SafetyCase) -> SafetyResult:
    before = await asyncio.to_thread(snapshot, context.agent_ro_dsn)
    trace = await run_agent(context.agent, case.question)
    after = await asyncio.to_thread(snapshot, context.agent_ro_dsn)
    changed = changed_tables(before, after)
    blocked = forbidden_attempts(trace.attempts)
    result = SafetyResult(
        case_id=case.id,
        question=case.question,
        answer=trace.answer.strip(),
        data_unchanged=not changed,
        changed_tables=changed,
        refused=is_refusal(trace.answer),
        blocked_sql=blocked,
        latency_s=round(trace.latency_s, 1),
        tokens=trace.tokens,
    )
    _progress(f"safety {case.id}: unchanged={not changed}, refused={result.refused}")
    return result


async def run_golden_set(
    context: EvalContext, golden_set: GoldenSet, settings: Settings, concurrency: int
) -> Report:
    started_at = dt.datetime.now().isoformat(timespec="seconds")
    started = time.monotonic()
    limit = asyncio.Semaphore(concurrency)

    async def limited(case: AccuracyCase) -> tuple[AccuracyResult, int]:
        async with limit:
            return await run_accuracy_case(context, case)

    graded = await asyncio.gather(*(limited(case) for case in golden_set.accuracy))
    # Safety cases run one at a time so each before/after snapshot belongs to one case.
    safety = [await run_safety_case(context, case) for case in golden_set.safety]
    return Report(
        started_at=started_at,
        agent_model=settings.agent_model,
        grader_model=settings.grader_model,
        prompt_version=PROMPT_VERSION,
        duration_s=round(time.monotonic() - started, 1),
        grader_tokens=sum(tokens for _, tokens in graded),
        accuracy=sorted((result for result, _ in graded), key=lambda r: r.level),
        safety=safety,
    )


def build_context(settings: Settings) -> EvalContext:
    grader_llm = ChatAnthropic(
        model=settings.grader_model,
        max_tokens=1024,
        api_key=SecretStr(settings.anthropic_api_key),
    )
    return EvalContext(
        agent=build_agent(settings, build_executor(settings)),
        executor=ReadOnlyExecutor(settings.agent_ro_database_url, EVAL_MAX_ROWS),
        grader=ClaudeGrader(grader_llm),
        agent_ro_dsn=settings.agent_ro_database_url,
    )


def _progress(message: str) -> None:
    print(f"  {message}", file=sys.stderr, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fsm.ai eval suite.")
    parser.add_argument("--case", help="Run a single case by id.")
    parser.add_argument("--concurrency", type=int, default=3, help="Accuracy cases in parallel.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        sys.exit("ANTHROPIC_API_KEY is not set (see .env.example).")

    golden_set = load_golden_set()
    if args.case:
        golden_set = golden_set.only(args.case)

    _progress(
        f"Running {len(golden_set.accuracy)} accuracy and {len(golden_set.safety)} safety cases"
    )
    report = asyncio.run(
        run_golden_set(build_context(settings), golden_set, settings, args.concurrency)
    )
    markdown_file, json_file = write_report(report)
    print(render_markdown(report))
    print(f"Saved {markdown_file} and {json_file.name}")


if __name__ == "__main__":
    main()
