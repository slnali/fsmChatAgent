-- Two schemas in one database:
--   data      the provided transaction data (agent: read only)
--   fsm_chat  application state: chats, messages, rules (app: read/write)
CREATE SCHEMA IF NOT EXISTS data;
CREATE SCHEMA IF NOT EXISTS fsm_chat;

-- Nobody gets anything implicitly via the public schema.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
