import pytest

from fsm_ai.migrations.runner import substitute_variables


def test_substitutes_and_quotes_variables() -> None:
    sql = "ALTER ROLE app PASSWORD :'password'; SELECT '{}'::jsonb, id::text"

    result = substitute_variables(sql, {"password": "it's"})

    assert result == "ALTER ROLE app PASSWORD 'it''s'; SELECT '{}'::jsonb, id::text"


def test_missing_variable_fails_loudly() -> None:
    with pytest.raises(KeyError, match="password"):
        substitute_variables("ALTER ROLE app PASSWORD :'password'", {})
