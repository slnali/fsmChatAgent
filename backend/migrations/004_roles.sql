-- Login roles. Passwords come from env: the migration runner substitutes the psql-style variables below.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fsm_agent_ro') THEN
        CREATE ROLE fsm_agent_ro LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fsm_app') THEN
        CREATE ROLE fsm_app LOGIN;
    END IF;
END
$$;

ALTER ROLE fsm_agent_ro PASSWORD :'fsm_agent_ro_password';
ALTER ROLE fsm_app PASSWORD :'fsm_app_password';

-- fsm_agent_ro: what the agent's SQL runs as. SELECT on data only, read-only, time-boxed.
GRANT USAGE ON SCHEMA data TO fsm_agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA data TO fsm_agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT SELECT ON TABLES TO fsm_agent_ro;
ALTER ROLE fsm_agent_ro SET default_transaction_read_only = on;
ALTER ROLE fsm_agent_ro SET statement_timeout = '15s';
ALTER ROLE fsm_agent_ro SET idle_in_transaction_session_timeout = '30s';

-- fsm_app: what the API uses for chats, messages and rules. Nothing on data.
GRANT USAGE ON SCHEMA fsm_chat TO fsm_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA fsm_chat TO fsm_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fsm_chat TO fsm_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA fsm_chat GRANT SELECT, INSERT, UPDATE ON TABLES TO fsm_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA fsm_chat GRANT USAGE, SELECT ON SEQUENCES TO fsm_app;
