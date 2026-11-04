"""End to end through the real API, DB and agent loop, with a scripted model."""

from collections.abc import Callable

import psycopg
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from tests.builders import (
    ScriptedChatModel,
    data_row_counts,
    event_names,
    events_named,
    propose_rule_reply,
    run_sql_reply,
    send_message,
    text_reply,
)
from tests.conftest import DatabaseUrls

MakeClient = Callable[[list[AIMessage]], tuple[TestClient, ScriptedChatModel]]
ITALY_RULE = (
    "t.merchant_location_id IN (SELECT id FROM data.merchant_locations WHERE state = 'Italy')"
)
FRAUD_BY_TYPE = (
    "SELECT t.transaction_type, SUM(fl.is_fraud::int) AS fraud FROM data.transactions t "
    "JOIN data.fraud_labels fl ON fl.transaction_id = t.id::text GROUP BY 1 ORDER BY 1"
)


def new_chat(client: TestClient) -> str:
    response = client.post("/chats")
    assert response.status_code == 201
    return response.json()["id"]


def test_explore_turn_streams_sql_results_and_answer_and_is_audited(
    make_client: MakeClient,
) -> None:
    client, model = make_client(
        [
            run_sql_reply(FRAUD_BY_TYPE, purpose="Fraud by type"),
            text_reply("**Chip** has all the fraud."),
        ]
    )
    chat_id = new_chat(client)

    events = send_message(client, chat_id, "Where is the fraud by transaction type?")

    assert event_names(events) == ["tool_call", "tool_result", "text_delta", "done"]
    assert events_named(events, "tool_call")[0] == {
        "id": "call_sql",
        "sql": FRAUD_BY_TYPE,
        "purpose": "Fraud by type",
    }
    result = events_named(events, "tool_result")[0]
    assert result["columns"] == ["transaction_type", "fraud"]
    assert result["rows"] == [
        ["Chip Transaction", 8],
        ["Online Transaction", 0],
        ["Swipe Transaction", 0],
    ]
    assert (
        "".join(e["text"] for e in events_named(events, "text_delta"))
        == "**Chip** has all the fraud."
    )
    # The model saw the tool result before answering.
    assert isinstance(model.received[1][-1], ToolMessage)

    chat = client.get(f"/chats/{chat_id}").json()
    assert chat["title"] == "Where is the fraud by transaction type?"
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant", "tool", "assistant"]
    assert chat["messages"][1]["metadata"]["model"] == "scripted"
    assert chat["messages"][1]["metadata"]["prompt_version"]
    assert chat["messages"][-1]["id"] == events_named(events, "done")[0]["message_id"]


def test_history_is_replayed_on_the_next_turn(make_client: MakeClient) -> None:
    client, model = make_client([text_reply("Hello."), text_reply("Still here.")])
    chat_id = new_chat(client)

    send_message(client, chat_id, "first question")
    send_message(client, chat_id, "second question")

    second_turn = model.received[1]
    assert [m.content for m in second_turn[1:]] == ["first question", "Hello.", "second question"]


def test_rule_proposal_reports_matches_and_fraud_rate(make_client: MakeClient) -> None:
    client, _ = make_client([propose_rule_reply(ITALY_RULE), text_reply("Proposed.")])
    chat_id = new_chat(client)

    events = send_message(client, chat_id, "Create a rule for the Italy fraud")

    proposal = events_named(events, "rule_proposal")[0]
    assert proposal["where_clause"] == ITALY_RULE
    assert (proposal["matched_count"], proposal["fraud_count"], proposal["fraud_rate"]) == (
        10,
        8,
        0.8,
    )


def test_fsm_saves_a_rule(make_client: MakeClient, database_urls: DatabaseUrls) -> None:
    client, _ = make_client([])
    chat_id = new_chat(client)

    response = client.post(
        "/rules",
        json={
            "chat_id": chat_id,
            "name": "Italy",
            "where_clause": ITALY_RULE,
            "rationale": "85% fraud",
        },
    )

    assert response.status_code == 201
    assert response.json()["matched_count"] == 10
    assert response.json()["fraud_rate"] == 0.8
    assert [r["name"] for r in client.get(f"/chats/{chat_id}").json()["rules"]] == ["Italy"]
    with psycopg.connect(database_urls.owner) as conn:
        assert conn.execute(
            "SELECT where_clause FROM fsm_chat.rules WHERE chat_id = %s", (chat_id,)
        ).fetchall() == [(ITALY_RULE,)]


def test_unsafe_rule_is_rejected(make_client: MakeClient, database_urls: DatabaseUrls) -> None:
    client, _ = make_client([])
    chat_id = new_chat(client)
    before = data_row_counts(database_urls.owner)

    response = client.post(
        "/rules",
        json={
            "chat_id": chat_id,
            "name": "evil",
            "where_clause": "1=1; DROP TABLE data.transactions",
        },
    )

    assert response.status_code == 422
    assert data_row_counts(database_urls.owner) == before


def test_malicious_tool_sql_is_blocked_and_data_unchanged(
    make_client: MakeClient, database_urls: DatabaseUrls
) -> None:
    client, _ = make_client(
        [run_sql_reply("DELETE FROM data.fraud_labels"), text_reply("I can't do that.")]
    )
    chat_id = new_chat(client)
    before = data_row_counts(database_urls.owner)

    events = send_message(client, chat_id, "Delete all fraud labels")

    assert "Rejected by SQL guard" in events_named(events, "tool_result")[0]["error"]
    assert data_row_counts(database_urls.owner) == before


def test_unknown_chat_returns_404(make_client: MakeClient) -> None:
    client, _ = make_client([])

    assert client.get("/chats/00000000-0000-0000-0000-000000000000").status_code == 404
