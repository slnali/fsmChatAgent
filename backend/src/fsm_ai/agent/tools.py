"""The agent's only two tools. Both are read-only; saving a rule is the FSM's job (POST /rules)."""

from dataclasses import dataclass
from typing import Any

from fsm_ai.agent.events import StreamEvent
from fsm_ai.data_access.readonly_executor import ReadOnlyExecutor, RuleEvaluationError

RUN_SQL = "run_sql"
PROPOSE_RULE = "propose_rule"

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": RUN_SQL,
        "description": (
            "Run one read-only PostgreSQL SELECT against the `data` schema and get the result "
            "(capped rows). Aggregate in SQL. The FSM sees the SQL, purpose and result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A single SELECT statement."},
                "purpose": {
                    "type": "string",
                    "description": "One short sentence: what this query checks and why.",
                },
            },
            "required": ["sql", "purpose"],
        },
    },
    {
        "name": PROPOSE_RULE,
        "description": (
            "Propose a fraud rule once a hypothesis is validated. The rule is a boolean WHERE "
            "clause over data.transactions aliased `t` (other tables only via subqueries; never "
            "data.fraud_labels). Returns how many transactions it matches and their fraud rate. "
            "Nothing is saved: the FSM decides whether to create it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short rule name."},
                "where_clause": {
                    "type": "string",
                    "description": "The condition only, without the WHERE keyword.",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this rule, citing the evidence found.",
                },
            },
            "required": ["name", "where_clause", "rationale"],
        },
    },
]


@dataclass(frozen=True)
class ToolOutcome:
    events: list[StreamEvent]
    result: dict[str, Any]  # stored in chat_messages and sent back to the model


class AgentTools:
    def __init__(self, executor: ReadOnlyExecutor) -> None:
        self._executor = executor

    def execute(self, call_id: str, name: str, args: dict[str, Any]) -> ToolOutcome:
        if name == RUN_SQL:
            return self._run_sql(call_id, str(args.get("sql", "")))
        if name == PROPOSE_RULE:
            return self._propose_rule(
                name=str(args.get("name", "")),
                where_clause=str(args.get("where_clause", "")),
                rationale=str(args.get("rationale", "")),
            )
        return ToolOutcome(events=[], result={"error": f"Unknown tool '{name}'."})

    def _run_sql(self, call_id: str, sql: str) -> ToolOutcome:
        result = self._executor.run(sql).to_dict()
        return ToolOutcome(
            events=[StreamEvent("tool_result", {"id": call_id, **result})], result=result
        )

    def _propose_rule(self, name: str, where_clause: str, rationale: str) -> ToolOutcome:
        try:
            metrics = self._executor.evaluate_rule(where_clause)
        except RuleEvaluationError as error:
            return ToolOutcome(events=[], result={"error": f"Invalid rule: {error}"})

        proposal = {
            "name": name,
            "where_clause": where_clause,
            "rationale": rationale,
            "matched_count": metrics.matched_count,
            "labelled_count": metrics.labelled_count,
            "fraud_count": metrics.fraud_count,
            "fraud_rate": metrics.fraud_rate,
        }
        return ToolOutcome(events=[StreamEvent("rule_proposal", proposal)], result=proposal)
