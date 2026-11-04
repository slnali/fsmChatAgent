CREATE TABLE fsm_chat.chats (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The audit trail: every user, assistant and tool message, in order.
CREATE TABLE fsm_chat.chat_messages (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id    UUID NOT NULL REFERENCES fsm_chat.chats (id),
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content    JSONB NOT NULL,
    metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX chat_messages_chat_id_idx ON fsm_chat.chat_messages (chat_id, id);

-- A rule is a WHERE clause on data.transactions, saved by the FSM (never by the agent).
CREATE TABLE fsm_chat.rules (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id       UUID NOT NULL REFERENCES fsm_chat.chats (id),
    name          TEXT NOT NULL,
    where_clause  TEXT NOT NULL,
    rationale     TEXT NOT NULL DEFAULT '',
    matched_count INTEGER NOT NULL,
    fraud_count   INTEGER NOT NULL,
    fraud_rate    NUMERIC,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX rules_chat_id_idx ON fsm_chat.rules (chat_id);
