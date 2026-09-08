"""Phase 3 — measurement correctness before the user test.

Covers the items picked up this round: telemetry attribution (D2), the fourth
"other" activity label (D3), per-activity retention, the writer-goal field, and
the scoped summary (D5).
"""
import json

from app.graph.nodes import _cognitive_fallback


def test_unmatched_message_is_other_not_planning():
    # D3: the old fallback returned "planning" for anything it couldn't place,
    # inflating the rarest category.
    assert _cognitive_fallback("thanks, that helps") == "other"
    assert _cognitive_fallback("ok sounds good") == "other"
    # a message that clearly names a writing activity still classifies
    assert _cognitive_fallback("what should happen next in the plot?") == "planning"
    assert _cognitive_fallback("give me feedback on this sentence") in {"translation", "reviewing"}


def _mk_student(client, name):
    u = client.post("/api/session", json={"display_name": name, "role": "student"}).json()
    return u["user_id"], {"X-User-Id": u["user_id"]}


def test_events_are_attributed_to_the_calling_student(client):
    # D2: events used to be filed under the first student in the table.
    uid_a, ha = _mk_student(client, "AttrA")
    uid_b, hb = _mk_student(client, "AttrB")
    ws_a = client.post("/api/workspaces", json={"title": "A"}, headers=ha).json()["workspace_id"]
    ws_b = client.post("/api/workspaces", json={"title": "B"}, headers=hb).json()["workspace_id"]

    client.post("/api/research/events",
                json={"workspace_id": ws_a, "event_type": "keystroke", "delta_change": 5},
                headers=ha)
    client.post("/api/research/events",
                json={"workspace_id": ws_b, "event_type": "paste", "delta_change": 200},
                headers=hb)

    # Export maps user_id -> Participant_NN; each workspace's events must carry
    # that workspace owner's participant code, not a single shared one.
    export = client.get("/api/research/export.json").json()
    part_of_ws = {w["workspace_id"]: w["participant"] for w in export["workspaces"]}
    for ev in export["telemetry_events"]:
        if ev["workspace_id"] in (ws_a, ws_b) and ev["event_type"] in ("keystroke", "paste"):
            assert ev["participant"] == part_of_ws[ev["workspace_id"]]
    assert part_of_ws[ws_a] != part_of_ws[ws_b]


def test_compare_and_summary_carry_retention_by_activity(client):
    cmp = client.get("/api/research/experiments/compare").json()
    for row in cmp["arms"]:
        assert set(row["retention_by_activity"]) == {
            "planning", "translation", "reviewing", "other"
        }
    summary = client.get("/api/research/summary").json()
    assert set(summary["retention_by_activity"]) == {
        "planning", "translation", "reviewing", "other"
    }


def test_writer_goal_persists_and_is_exported(client):
    uid, h = _mk_student(client, "GoalTester")
    ws = client.post(
        "/api/workspaces",
        json={"title": "G", "mode": "educational_narrative",
              "goals": "Make the ending ambiguous, not tidy."},
        headers=h,
    ).json()
    assert ws["goals"] == "Make the ending ambiguous, not tidy."

    ws2 = client.patch(f"/api/workspaces/{ws['workspace_id']}",
                       json={"goals": "Keep it under 300 words."}).json()
    assert ws2["goals"] == "Keep it under 300 words."

    export = client.get("/api/research/export.json").json()
    w = next(x for x in export["workspaces"] if x["workspace_id"] == ws["workspace_id"])
    assert w["goals"] == "Keep it under 300 words."


def test_summary_can_be_scoped_to_one_workspace(client):
    uid, h = _mk_student(client, "ScopeTester")
    w1 = client.post("/api/workspaces", json={"title": "S1"}, headers=h).json()["workspace_id"]
    w2 = client.post("/api/workspaces", json={"title": "S2"}, headers=h).json()["workspace_id"]

    whole = client.get("/api/research/summary").json()
    scoped = client.get(f"/api/research/summary?workspace_id={w1}").json()

    assert whole["workspaces"] >= 2
    assert scoped["workspaces"] == 1
    assert all(pw["workspace_id"] == w1 for pw in scoped["per_workspace"])
