from typing import Any
from uuid import UUID

from fsm_ai.persistence.database import AppDatabase

TITLE_MAX_LENGTH = 80


class ChatRepo:
    def __init__(self, db: AppDatabase) -> None:
        self._db = db

    def create(self) -> UUID:
        with self._db.connect() as conn:
            row = conn.execute("INSERT INTO fsm_chat.chats DEFAULT VALUES RETURNING id").fetchone()
        assert row is not None
        return row["id"]

    def get(self, chat_id: UUID) -> dict[str, Any] | None:
        with self._db.connect() as conn:
            return conn.execute(
                "SELECT id, title, created_at FROM fsm_chat.chats WHERE id = %s", (chat_id,)
            ).fetchone()

    def set_title_if_missing(self, chat_id: UUID, first_message: str) -> None:
        title = " ".join(first_message.split())[:TITLE_MAX_LENGTH]
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE fsm_chat.chats SET title = %s WHERE id = %s AND title IS NULL",
                (title, chat_id),
            )
