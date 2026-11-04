from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from psycopg.types.json import Jsonb

from fsm_ai.persistence.database import AppDatabase

Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class NewMessage:
    role: Role
    content: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageRepo:
    """chat_messages is the audit trail: every user, assistant and tool message, in order."""

    def __init__(self, db: AppDatabase) -> None:
        self._db = db

    def add(self, chat_id: UUID, message: NewMessage) -> int:
        return self.add_many(chat_id, [message])[-1]

    def add_many(self, chat_id: UUID, messages: list[NewMessage]) -> list[int]:
        ids: list[int] = []
        with self._db.connect() as conn, conn.transaction():
            for message in messages:
                row = conn.execute(
                    "INSERT INTO fsm_chat.chat_messages (chat_id, role, content, metadata)"
                    " VALUES (%s, %s, %s, %s) RETURNING id",
                    (chat_id, message.role, Jsonb(message.content), Jsonb(message.metadata)),
                ).fetchone()
                assert row is not None
                ids.append(row["id"])
        return ids

    def list_for_chat(self, chat_id: UUID) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            return conn.execute(
                "SELECT id, role, content, metadata, created_at FROM fsm_chat.chat_messages"
                " WHERE chat_id = %s ORDER BY id",
                (chat_id,),
            ).fetchall()
