"""Phase 2 — activity-conditioned behaviour + the writer's Monitor.

The client's request #1: the Socratic Tutor behaves differently during
Planning, Translating and Reviewing, and the writer can declare which one they
are in (Flower & Hayes' Monitor). Activities are never a sequence.
"""
import json

from app import prompts

TUTOR_ROLE = {
    "base_prompt": prompts.BASE_SYSTEM_PROMPT,
    "planning_prompt": prompts.TUTOR_PLANNING_FRAGMENT,
    "translating_prompt": prompts.TUTOR_TRANSLATING_FRAGMENT,
    "reviewing_prompt": prompts.TUTOR_REVIEWING_FRAGMENT,
    "may_produce_prose": False, "enforcement_level": 2,
}


def test_activity_fragment_maps_every_spelling_to_its_column():
    f = prompts.activity_fragment
    assert f(TUTOR_ROLE, "planning") == prompts.TUTOR_PLANNING_FRAGMENT.strip()
    # detected spelling and declared spelling both resolve to the same column
    assert f(TUTOR_ROLE, "translation") == prompts.TUTOR_TRANSLATING_FRAGMENT.strip()
    assert f(TUTOR_ROLE, "translating") == prompts.TUTOR_TRANSLATING_FRAGMENT.strip()
    assert f(TUTOR_ROLE, "reviewing") == prompts.TUTOR_REVIEWING_FRAGMENT.strip()
    # unrecognised / "other" / empty -> no fragment
    assert f(TUTOR_ROLE, "other") == ""
    assert f(TUTOR_ROLE, "") == ""
    assert f(None, "planning") == ""


def test_prompt_is_materially_different_per_activity():
    plan = prompts.build_system_prompt(
        "educational_narrative", 2, False, "", "balanced", TUTOR_ROLE, "planning")
    review = prompts.build_system_prompt(
        "educational_narrative", 2, False, "", "balanced", TUTOR_ROLE, "reviewing")
    none = prompts.build_system_prompt(
        "educational_narrative", 2, False, "", "balanced", TUTOR_ROLE, "")

    assert plan != review
    assert "WRITING ACTIVITY — PLANNING" in plan
    assert "WRITING ACTIVITY — REVIEWING" in review
    assert "WRITING ACTIVITY" not in none  # no activity -> base prompt only


def _turn(client, ws, headers, message, declared=""):
    body = {"message": message, "draft": DRAFT}
    if declared:
        body["declared_activity"] = declared
    r = client.post(f"/api/workspaces/{ws}/turn", json=body, headers=headers)
    return json.loads(
        [ln for ln in r.text.splitlines() if ln.startswith("data:")][-1][5:]
    )


DRAFT = ("Captain Sarah stood on the red plain as the storm cleared and the "
         "engine telemetry stayed silent for one long moment.")


def test_declared_activity_changes_the_reply_under_one_role(client):
    u = client.post("/api/session",
                    json={"display_name": "MonitorTester", "role": "student"}).json()
    h = {"X-User-Id": u["user_id"]}
    ws = client.post("/api/workspaces",
                     json={"title": "M", "mode": "educational_narrative"},
                     headers=h).json()["workspace_id"]

    plan = _turn(client, ws, h, "How do I make this land?", declared="planning")
    review = _turn(client, ws, h, "How do I make this land?", declared="reviewing")

    assert plan["effective_activity"] == "planning"
    assert review["effective_activity"] == "reviewing"
    assert plan["response_text"] != review["response_text"]


def test_no_declaration_falls_back_to_the_detected_activity(client):
    u = client.post("/api/session",
                    json={"display_name": "FallbackTester", "role": "student"}).json()
    h = {"X-User-Id": u["user_id"]}
    ws = client.post("/api/workspaces",
                     json={"title": "F", "mode": "educational_narrative"},
                     headers=h).json()["workspace_id"]

    d = _turn(client, ws, h, "Is my pacing off in this paragraph?")
    assert d["declared_activity"] == ""
    assert d["effective_activity"] == d["cognitive"]  # detected drives it


def test_declared_and_detected_are_both_persisted_and_exported(client):
    u = client.post("/api/session",
                    json={"display_name": "ExportTester", "role": "student"}).json()
    h = {"X-User-Id": u["user_id"]}
    ws = client.post("/api/workspaces",
                     json={"title": "X", "mode": "educational_narrative"},
                     headers=h).json()["workspace_id"]
    _turn(client, ws, h, "What is this scene assuming?", declared="reviewing")

    turns = client.get(f"/api/workspaces/{ws}/turns").json()
    user_turn = next(t for t in turns if t["speaker"] == "user")
    assert user_turn["declared_activity"] == "reviewing"
    assert "cognitive_activity" in user_turn  # detected still there

    export = client.get("/api/research/export.json").json()
    assert export["export_meta"]["schema_version"] == "1.1"
    assert all("declared_activity" in t for t in export["conversation_turns"])

    tl = client.get(f"/api/research/timeline?workspace_id={ws}").json()["points"]
    assert tl and all("declared" in p for p in tl)
