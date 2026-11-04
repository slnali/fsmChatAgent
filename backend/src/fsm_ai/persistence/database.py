from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg.rows import DictRow, dict_row


class AppDatabase:
    """Connections as fsm_app: read/write on fsm_chat, nothing on data."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def connect(self) -> Generator[psycopg.Connection[DictRow]]:
        with psycopg.Connection[DictRow].connect(self._dsn, row_factory=dict_row) as conn:
            yield conn
