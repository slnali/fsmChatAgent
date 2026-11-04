from fsm_ai.data_access.readonly_executor import ReadOnlyExecutor


def test_caps_rows_and_flags_truncation(executor: ReadOnlyExecutor) -> None:
    result = executor.run("SELECT id FROM data.transactions ORDER BY id")

    assert result.error is None
    assert result.columns == ["id"]
    assert result.rows == [[1], [2], [3], [4], [5]]
    assert result.truncated is True


def test_returns_postgres_errors_as_results(executor: ReadOnlyExecutor) -> None:
    result = executor.run("SELECT no_such_column FROM data.transactions")

    assert result.error is not None
    assert "no_such_column" in result.error


def test_evaluates_rule_against_labelled_transactions(executor: ReadOnlyExecutor) -> None:
    metrics = executor.evaluate_rule(
        "t.merchant_location_id IN (SELECT id FROM data.merchant_locations WHERE state = 'Italy')"
    )

    assert (metrics.matched_count, metrics.labelled_count, metrics.fraud_count) == (10, 10, 8)
    assert metrics.fraud_rate == 0.8
