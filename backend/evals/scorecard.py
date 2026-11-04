"""Per-stage scorecard. There is no overall pass/fail: each stage of each case is shown, so you
can see exactly where a case went wrong."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from evals.compare import Outcome

REPORTS_DIR = Path(__file__).parent / "reports"

SqlStatus = Literal["ran", "error", "no_sql"]


@dataclass(frozen=True)
class AccuracyResult:
    case_id: str
    level: int
    question: str
    answer: str
    golden_sql: str
    agent_sql: str | None
    sql_status: SqlStatus
    comparison: Outcome
    comparison_detail: str
    score: float
    explanation: str
    latency_s: float
    tokens: int
    queries_run: int


@dataclass(frozen=True)
class SafetyResult:
    case_id: str
    question: str
    answer: str
    data_unchanged: bool
    changed_tables: list[str]
    refused: bool
    blocked_sql: list[str]
    latency_s: float
    tokens: int


@dataclass(frozen=True)
class Report:
    started_at: str
    agent_model: str
    grader_model: str
    prompt_version: str
    duration_s: float
    grader_tokens: int
    accuracy: list[AccuracyResult] = field(default_factory=list)
    safety: list[SafetyResult] = field(default_factory=list)

    @property
    def agent_tokens(self) -> int:
        return sum(r.tokens for r in self.accuracy) + sum(r.tokens for r in self.safety)


SQL_STATUS = {"ran": "✅ ran", "error": "❌ error", "no_sql": "❌ no SQL"}
COMPARISON = {
    "exact": "✅ exact",
    "superset": "✅ superset",
    "mismatch": "❌ mismatch",
    "error": "❌ error",
}


def render_markdown(report: Report) -> str:
    lines = [
        f"# fsm.ai eval scorecard — {report.started_at}",
        "",
        "## Accuracy cases",
        "| # | Case | 1. Agent SQL | 2. Result comparison | 3. Grader | Grader explanation "
        "| Latency | Tokens |",
        "|---|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r.level} | {r.case_id} | {SQL_STATUS[r.sql_status]} | {COMPARISON[r.comparison]} "
        f"| {r.score:.2f} | {_cell(r.explanation)} | {r.latency_s:.1f}s | {_tokens(r.tokens)} |"
        for r in report.accuracy
    ]
    lines += [
        "",
        "## Safety cases",
        "| # | Case | Data unchanged | Agent refused | Forbidden SQL attempted |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {i} | {r.case_id} | {_tick(r.data_unchanged)} | {_tick(r.refused)} "
        f"| {_blocked(r.blocked_sql)} |"
        for i, r in enumerate(report.safety, start=1)
    ]
    lines += [
        "",
        f"Agent model `{report.agent_model}` · grader `{report.grader_model}` · "
        f"prompt `{report.prompt_version}` · agent tokens {_tokens(report.agent_tokens)} · "
        f"grader tokens {_tokens(report.grader_tokens)} · run time {report.duration_s:.0f}s",
    ]
    if report.accuracy:
        lines += ["", "## Agent SQL", ""]
        for r in report.accuracy:
            lines += [f"**{r.case_id}** — {r.question}", "", "```sql", r.agent_sql or "-", "```"]
    return "\n".join(lines) + "\n"


def write_report(report: Report, reports_dir: Path = REPORTS_DIR) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = report.started_at.replace(":", "-")
    markdown_file = reports_dir / f"{stem}.md"
    json_file = reports_dir / f"{stem}.json"
    markdown_file.write_text(render_markdown(report))
    json_file.write_text(json.dumps(asdict(report), indent=2) + "\n")
    return markdown_file, json_file


def _tick(ok: bool) -> str:
    return "✅" if ok else "❌"


def _blocked(blocked_sql: list[str]) -> str:
    return f"yes, {len(blocked_sql)} blocked" if blocked_sql else "no"


def _tokens(count: int) -> str:
    return f"{count / 1000:.1f}k" if count >= 1000 else str(count)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")
