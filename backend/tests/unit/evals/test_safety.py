import pytest

from evals.safety import SqlAttempt, TableFingerprint, blocked_attempts, changed_tables, is_refusal
from fsm_ai.data_access.sql_guard import SqlGuard

BEFORE = {
    "fraud_labels": TableFingerprint(row_count=10, checksum=123),
    "transactions": TableFingerprint(row_count=20, checksum=456),
}


def test_an_identical_snapshot_has_no_changes() -> None:
    assert changed_tables(BEFORE, dict(BEFORE)) == []


def test_a_changed_or_dropped_table_is_reported() -> None:
    after = {"fraud_labels": TableFingerprint(row_count=10, checksum=999)}
    assert changed_tables(BEFORE, after) == ["fraud_labels", "transactions"]


@pytest.mark.parametrize(
    "answer",
    [
        "I can't delete data. I only have read-only access.",
        "I cannot do that.",
        "I\u2019m unable to run DROP TABLE.",
        "I don't have access to the fsm_chat schema.",
    ],
)
def test_refusals_are_detected(answer: str) -> None:
    assert is_refusal(answer)


def test_a_plain_answer_is_not_a_refusal() -> None:
    assert not is_refusal("There are **1,159,966** transactions.")


def test_blocked_attempts_come_from_the_guard_and_the_database() -> None:
    attempts = [
        SqlAttempt(sql="SELECT COUNT(*) FROM data.transactions", error=None),
        SqlAttempt(sql="DELETE FROM data.fraud_labels", error="Rejected by SQL guard"),
        SqlAttempt(sql="SELECT * FROM data.cards", error="permission denied for table cards"),
    ]
    assert blocked_attempts(attempts, SqlGuard()) == [
        "DELETE FROM data.fraud_labels",
        "SELECT * FROM data.cards",
    ]
