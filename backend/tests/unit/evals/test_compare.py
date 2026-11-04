from typing import Any

from evals.compare import compare_results
from fsm_ai.data_access.readonly_executor import QueryResult


def result(columns: list[str], *rows: list[Any]) -> QueryResult:
    return QueryResult(columns=columns, rows=[list(row) for row in rows], row_count=len(rows))


GOLDEN = result(["transaction_type", "fraud_rate"], ["Chip", 0.0021], ["Online", 0.0])


def test_same_values_are_an_exact_match() -> None:
    assert compare_results(GOLDEN, GOLDEN).outcome == "exact"


def test_row_order_is_ignored() -> None:
    generated = result(["transaction_type", "fraud_rate"], ["Online", 0.0], ["Chip", 0.0021])
    assert compare_results(GOLDEN, generated).outcome == "exact"


def test_floats_match_within_tolerance() -> None:
    generated = result(["transaction_type", "fraud_rate"], ["Chip", 0.00210004], ["Online", 0.0])
    assert compare_results(GOLDEN, generated).outcome == "exact"


def test_values_the_agent_rounded_match() -> None:
    golden = result(["transaction_type", "fraud_rate"], ["Chip", 0.00092915], ["Online", 0.0])
    generated = result(["transaction_type", "fraud_pct"], ["Chip", 0.093], ["Online", 0.0])
    assert compare_results(golden, generated).outcome == "exact"


def test_coarse_rounding_is_not_accepted() -> None:
    golden = result(["fraud_rate"], [0.14])
    generated = result(["fraud_rate"], [0.1])
    assert compare_results(golden, generated).outcome == "mismatch"


def test_column_names_and_order_are_ignored() -> None:
    generated = result(["rate", "type"], [0.0021, "Chip"], [0.0, "Online"])
    assert compare_results(GOLDEN, generated).outcome == "exact"


def test_a_percentage_matches_a_fraction() -> None:
    generated = result(["transaction_type", "fraud_pct"], ["Chip", 0.21], ["Online", 0.0])
    assert compare_results(GOLDEN, generated).outcome == "exact"


def test_extra_columns_are_a_superset() -> None:
    generated = result(
        ["transaction_type", "transactions", "fraud_rate"],
        ["Chip", 1000, 0.0021],
        ["Online", 500, 0.0],
    )
    comparison = compare_results(GOLDEN, generated)
    assert comparison.outcome == "superset"
    assert "1 extra column" in comparison.detail


def test_different_values_are_a_mismatch() -> None:
    generated = result(["transaction_type", "fraud_rate"], ["Chip", 0.5], ["Online", 0.0])
    assert compare_results(GOLDEN, generated).outcome == "mismatch"


def test_values_in_the_wrong_rows_are_a_mismatch() -> None:
    golden = result(["type", "rate"], ["Chip", 0.1], ["Online", 0.2])
    generated = result(["type", "rate"], ["Chip", 0.2], ["Online", 0.1])
    assert compare_results(golden, generated).outcome == "mismatch"


def test_a_different_row_count_is_a_mismatch() -> None:
    generated = result(["transaction_type", "fraud_rate"], ["Chip", 0.0021])
    assert "Expected 2 rows, got 1" in compare_results(GOLDEN, generated).detail


def test_an_agent_sql_error_is_an_error() -> None:
    failed = QueryResult(error="column t.typo does not exist")
    comparison = compare_results(GOLDEN, failed)
    assert comparison.outcome == "error"
    assert "typo" in comparison.detail


def test_types_are_normalised() -> None:
    golden = result(["dark_web", "n", "month"], [False, 3, "2019-01-01T00:00:00"])
    generated = result(["dark_web", "n", "month"], [0, 3.0, "2019-01-01"])
    assert compare_results(golden, generated).outcome == "exact"
