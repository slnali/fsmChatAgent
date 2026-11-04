"""Claude as the grader: given both SQLs, both results and the comparator signal, it scores
the agent's answer and explains why. It catches acceptable variation the comparator cannot."""

import json
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from evals.compare import Comparison
from fsm_ai.data_access.readonly_executor import QueryResult

GRADER_ROWS = 20

GRADER_PROMPT = """\
You grade a text-to-SQL agent used by fraud analysts on a PostgreSQL transactions database.
Compare the agent's SQL, result and answer with the golden SQL and result for the question.

Score from 0 to 1:
- 1.0: the agent's result answers the question as well as the golden result (different
  column names, row order, extra columns, rounding, or a percentage instead of a fraction
  are all fine).
- 0.5-0.9: a valid but different interpretation, or a correct result with a misleading answer.
- 0.0-0.4: wrong numbers, a wrong join or filter, the wrong denominator, or no usable result.

The deterministic comparator's verdict is a strong signal but can be fooled by formatting.
Keep the explanation to one or two sentences and name the specific problem, if any.
"""


class Verdict(BaseModel):
    score: float = Field(ge=0, le=1, description="0 = wrong, 1 = fully correct.")
    explanation: str = Field(description="One or two sentences.")


@dataclass(frozen=True)
class Grade:
    score: float
    explanation: str
    tokens: int


class Grader(Protocol):
    def grade(
        self,
        question: str,
        golden_sql: str,
        golden: QueryResult,
        agent_sql: str | None,
        generated: QueryResult | None,
        answer: str,
        comparison: Comparison,
    ) -> Grade: ...


class ClaudeGrader:
    def __init__(self, llm: BaseChatModel) -> None:
        # Sonnet 5.5 does not support forced tool calling, so use native JSON schema output.
        self._llm = llm.with_structured_output(Verdict, method="json_schema", include_raw=True)

    def grade(
        self,
        question: str,
        golden_sql: str,
        golden: QueryResult,
        agent_sql: str | None,
        generated: QueryResult | None,
        answer: str,
        comparison: Comparison,
    ) -> Grade:
        case = {
            "question": question,
            "golden_sql": golden_sql.strip(),
            "golden_result": _preview(golden),
            "agent_sql": agent_sql,
            "agent_result": _preview(generated) if generated else None,
            "agent_answer": answer,
            "comparator": {"outcome": comparison.outcome, "detail": comparison.detail},
        }
        response = self._llm.invoke(
            [("system", GRADER_PROMPT), ("human", json.dumps(case, indent=2, default=str))]
        )
        assert isinstance(response, dict)
        verdict = response["parsed"]
        if not isinstance(verdict, Verdict):
            return Grade(0.0, f"The grader returned no verdict: {response['parsing_error']}", 0)
        usage = getattr(response["raw"], "usage_metadata", None) or {}
        return Grade(verdict.score, verdict.explanation, usage.get("total_tokens", 0))


def _preview(result: QueryResult) -> dict[str, Any]:
    return {
        "columns": result.columns,
        "rows": result.rows[:GRADER_ROWS],
        "total_rows": len(result.rows),
        "error": result.error,
    }
