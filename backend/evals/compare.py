"""Deterministic comparison of the agent's result set with the golden one.

Results are compared by value, never by SQL text. Row order and column names are ignored,
extra agent columns are allowed (superset), numbers match within a small tolerance or the
precision the agent rounded to, and a rate column may be a fraction or a percentage.
"""

import itertools
import math
from dataclasses import dataclass
from typing import Any, Literal

from fsm_ai.data_access.readonly_executor import QueryResult

Outcome = Literal["exact", "superset", "mismatch", "error"]

REL_TOLERANCE = 1e-3
ABS_TOLERANCE = 1e-6
SCALES = (1.0, 100.0)  # a fraction or the same value as a percentage
MIN_ROUNDED_DECIMALS = 2  # ROUND(x, 2) or finer counts as deliberate rounding


@dataclass(frozen=True)
class Comparison:
    outcome: Outcome
    detail: str


@dataclass(frozen=True)
class _ColumnMatch:
    index: int
    scale: float


def compare_results(golden: QueryResult, generated: QueryResult) -> Comparison:
    if golden.error:
        return Comparison("error", f"Golden SQL failed: {golden.error}")
    if generated.error:
        return Comparison("error", f"Agent SQL failed: {generated.error}")
    if golden.truncated or generated.truncated:
        return Comparison("error", "A result was truncated; raise the eval row cap.")
    if len(golden.rows) != len(generated.rows):
        return Comparison(
            "mismatch", f"Expected {len(golden.rows)} rows, got {len(generated.rows)}."
        )

    golden_rows = [[_normalise(value) for value in row] for row in golden.rows]
    generated_rows = [[_normalise(value) for value in row] for row in generated.rows]
    candidates = [
        _candidate_columns(_column(golden_rows, index), generated_rows, len(generated.columns))
        for index in range(len(golden.columns))
    ]
    for column, options in zip(golden.columns, candidates, strict=True):
        if not options:
            return Comparison("mismatch", f"No agent column has the values of '{column}'.")

    for mapping in itertools.product(*candidates):
        if len({match.index for match in mapping}) != len(mapping):
            continue
        expected = [_scale_row(row, mapping) for row in golden_rows]
        projected = [[row[match.index] for match in mapping] for row in generated_rows]
        if _same_rows(expected, projected):
            if len(generated.columns) == len(golden.columns):
                return Comparison("exact", "Same values.")
            extra = len(generated.columns) - len(golden.columns)
            return Comparison("superset", f"Same values, plus {extra} extra column(s).")
    return Comparison("mismatch", "Every column has a match, but the rows do not line up.")


def _normalise(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        return text.removesuffix("T00:00:00")  # a timestamp at midnight equals the date
    return value


def _column(rows: list[list[Any]], index: int) -> list[Any]:
    return [row[index] for row in rows]


def _candidate_columns(
    golden_values: list[Any], generated_rows: list[list[Any]], width: int
) -> list[_ColumnMatch]:
    matches: list[_ColumnMatch] = []
    for index in range(width):
        values = _column(generated_rows, index)
        for scale in SCALES:
            if scale != 1.0 and not all(_is_number(value) for value in golden_values):
                continue
            scaled = [_scale(value, scale) for value in golden_values]
            if _same_values(sorted(scaled, key=_sort_key), sorted(values, key=_sort_key)):
                matches.append(_ColumnMatch(index, scale))
    return matches


def _scale_row(row: list[Any], mapping: tuple[_ColumnMatch, ...]) -> list[Any]:
    """Puts golden values on the agent's scale (for example a fraction as a percentage)."""
    return [_scale(value, match.scale) for value, match in zip(row, mapping, strict=True)]


def _same_rows(expected: list[list[Any]], actual: list[list[Any]]) -> bool:
    expected_sorted = sorted(expected, key=_row_key)
    actual_sorted = sorted(actual, key=_row_key)
    return all(_same_values(a, b) for a, b in zip(expected_sorted, actual_sorted, strict=True))


def _same_values(expected: list[Any], actual: list[Any]) -> bool:
    return len(expected) == len(actual) and all(
        _equal(a, b) for a, b in zip(expected, actual, strict=True)
    )


def _equal(expected: Any, actual: Any) -> bool:
    if _is_number(expected) and _is_number(actual):
        return math.isclose(expected, actual, rel_tol=REL_TOLERANCE, abs_tol=ABS_TOLERANCE) or abs(
            expected - actual
        ) <= _rounding_tolerance(actual)
    return expected == actual


def _rounding_tolerance(value: float) -> float:
    """Half a unit in the last decimal place of a value the agent rounded, else 0."""
    text = repr(value)
    if "e" in text or "." not in text:
        return 0.0
    decimals = len(text.split(".")[1])
    if decimals < MIN_ROUNDED_DECIMALS:
        return 0.0
    return 0.5 * 10**-decimals * (1 + 1e-9)


def _is_number(value: Any) -> bool:
    return isinstance(value, float)


def _scale(value: Any, factor: float) -> Any:
    return value * factor if _is_number(value) else value


def _sort_key(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, 0)
    if _is_number(value):
        return (1, value)
    return (2, str(value))


def _row_key(row: list[Any]) -> list[tuple[int, Any]]:
    return [_sort_key(value) for value in row]
