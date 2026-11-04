"""The golden set schema and loader."""

from pathlib import Path

import yaml
from pydantic import BaseModel

GOLDEN_SET_FILE = Path(__file__).parent / "golden_set.yaml"


class AccuracyCase(BaseModel):
    id: str
    level: int
    tests: str
    question: str
    golden_sql: str


class SafetyCase(BaseModel):
    id: str
    tests: str
    question: str


class GoldenSet(BaseModel):
    accuracy: list[AccuracyCase]
    safety: list[SafetyCase]

    def only(self, case_id: str) -> "GoldenSet":
        selected = GoldenSet(
            accuracy=[case for case in self.accuracy if case.id == case_id],
            safety=[case for case in self.safety if case.id == case_id],
        )
        if not selected.accuracy and not selected.safety:
            raise ValueError(f"Unknown case '{case_id}'.")
        return selected


def load_golden_set(path: Path = GOLDEN_SET_FILE) -> GoldenSet:
    return GoldenSet.model_validate(yaml.safe_load(path.read_text()))
