from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fsm_ai.persistence.database import AppDatabase


@dataclass(frozen=True)
class NewRule:
    chat_id: UUID
    name: str
    where_clause: str
    rationale: str
    matched_count: int
    fraud_count: int
    fraud_rate: float | None


class RuleRepo:
    def __init__(self, db: AppDatabase) -> None:
        self._db = db

    def add(self, rule: NewRule) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute(
                "INSERT INTO fsm_chat.rules"
                " (chat_id, name, where_clause, rationale, matched_count, fraud_count, fraud_rate)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " RETURNING id, chat_id, name, where_clause, rationale, matched_count,"
                " fraud_count, fraud_rate::float AS fraud_rate, created_at",
                (
                    rule.chat_id,
                    rule.name,
                    rule.where_clause,
                    rule.rationale,
                    rule.matched_count,
                    rule.fraud_count,
                    rule.fraud_rate,
                ),
            ).fetchone()
        assert row is not None
        return row

    def list_for_chat(self, chat_id: UUID) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            return conn.execute(
                "SELECT id, chat_id, name, where_clause, rationale, matched_count, fraud_count,"
                " fraud_rate::float AS fraud_rate, created_at"
                " FROM fsm_chat.rules WHERE chat_id = %s ORDER BY id",
                (chat_id,),
            ).fetchall()
