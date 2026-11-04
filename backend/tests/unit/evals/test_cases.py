import pytest

from evals.cases import load_golden_set


def test_the_golden_set_loads() -> None:
    golden_set = load_golden_set()
    assert [case.level for case in golden_set.accuracy] == [1, 2, 3, 4, 5, 6]
    assert len(golden_set.safety) == 3


def test_a_single_case_can_be_selected() -> None:
    selected = load_golden_set().only("count_transactions")
    assert [case.id for case in selected.accuracy] == ["count_transactions"]
    assert selected.safety == []


def test_an_unknown_case_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown case"):
        load_golden_set().only("nope")
