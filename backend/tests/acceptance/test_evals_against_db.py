import psycopg
import pytest

from evals.cases import load_golden_set
from evals.safety import changed_tables, snapshot
from fsm_ai.data_access.readonly_executor import ReadOnlyExecutor
from tests.conftest import DatabaseUrls

GOLDEN_SET = load_golden_set()


@pytest.mark.parametrize("case", GOLDEN_SET.accuracy, ids=lambda case: case.id)
def test_every_golden_sql_runs(executor: ReadOnlyExecutor, case) -> None:  # type: ignore[no-untyped-def]
    assert executor.run(case.golden_sql).error is None


def test_a_snapshot_detects_a_data_change(database_urls: DatabaseUrls) -> None:
    before = snapshot(database_urls.agent_ro)
    assert changed_tables(before, snapshot(database_urls.agent_ro)) == []

    with psycopg.connect(database_urls.owner, autocommit=True) as conn:
        conn.execute("INSERT INTO data.mcc_codes (mcc, description) VALUES (9999, 'Temp')")
        try:
            assert changed_tables(before, snapshot(database_urls.agent_ro)) == ["mcc_codes"]
        finally:
            conn.execute("DELETE FROM data.mcc_codes WHERE mcc = 9999")
