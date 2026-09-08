"""Phase 1 — "roles become data" — acceptance checks.

The iteration-2 plan is explicit that Phase 1 changes no behaviour: the seam
moves the two existing conditions into editable `AIRole` rows, and everything
a student sees must be byte-for-byte identical to the pre-role system.
"""
import json

from app import prompts

# The two seed roles, as dicts, mirroring what `ensure_default_roles` writes.
TUTOR_ROLE = {
    "base_prompt": prompts.BASE_SYSTEM_PROMPT,
    "planning_prompt": "", "translating_prompt": "", "reviewing_prompt": "",
    "may_produce_prose": False, "enforcement_level": 2,
    "archetype": "tutor", "behaviour": "socratic_questioning",
}
GHOST_ROLE = {
    "base_prompt": prompts.CONTROL_SYSTEM_PROMPT,
    "planning_prompt": "", "translating_prompt": "", "reviewing_prompt": "",
    "may_produce_prose": True, "enforcement_level": 0,
    "archetype": "ghost", "behaviour": "direct_generation",
}


def test_role_prompt_is_byte_identical_to_legacy_path():
    """build_system_prompt via a role record == the old module-constant path."""
    for mode in ("learning_scenario", "educational_narrative", "design_fiction"):
        for intercepted in (False, True):
            for intensity in ("light", "balanced", "deep"):
                legacy = prompts.build_system_prompt(
                    mode, 2, intercepted, "", intensity, None, "")
                via_role = prompts.build_system_prompt(
                    mode, 2, intercepted, "", intensity, TUTOR_ROLE, "")
                assert legacy == via_role, (mode, intercepted, intensity, "tutor")

                legacy_g = prompts.build_system_prompt(
                    mode, 0, intercepted, "", intensity, None, "")
                via_role_g = prompts.build_system_prompt(
                    mode, 0, intercepted, "", intensity, GHOST_ROLE, "")
                assert legacy_g == via_role_g, (mode, intercepted, intensity, "ghost")


def test_two_roles_are_seeded(client):
    by_arch = {r["archetype"]: r for r in client.get("/api/research/roles").json()}
    assert by_arch["tutor"]["may_produce_prose"] is False
    assert by_arch["tutor"]["enforcement_level"] == 2
    assert by_arch["ghost"]["may_produce_prose"] is True
    assert by_arch["ghost"]["enforcement_level"] == 0


def test_seeded_arms_each_carry_a_role(client):
    arms = client.get("/api/research/experiments").json()
    assert arms and all(a["role_id"] for a in arms)
    guard = next(a for a in arms if not a["is_control"])
    assert guard["role_name"] == "Socratic Tutor"


def test_graph_trace_uses_the_new_node_names(client):
    ids = [n["id"] for n in client.get("/api/graph").json()["nodes"]]
    assert ids == [
        "intent_classifier", "role_arbiter", "response_engine",
        "response_formatter", "agency_enforcer",
    ]


def test_role_edit_is_append_only_and_repoints_arms(client):
    tutor = next(r for r in client.get("/api/research/roles").json()
                 if r["archetype"] == "tutor")
    guard = next(a for a in client.get("/api/research/experiments").json()
                 if a["role_id"] == tutor["role_id"])

    new = client.patch(
        f"/api/research/roles/{tutor['role_id']}",
        json={"planning_prompt": "During planning, ask about goals."},
    ).json()

    assert new["version"] == tutor["version"] + 1
    assert new["parent_role_id"] == tutor["role_id"]
    assert new["role_id"] != tutor["role_id"]

    old = next(r for r in client.get("/api/research/roles").json()
               if r["role_id"] == tutor["role_id"])
    assert old["planning_prompt"] == ""  # untouched

    guard_after = next(a for a in client.get("/api/research/experiments").json()
                       if a["arm_id"] == guard["arm_id"])
    assert guard_after["role_id"] == new["role_id"]


def test_new_condition_defaults_to_the_tutor_role(client):
    created = client.post("/api/research/experiments",
                          json={"name": "Fresh condition"}).json()
    assert created["role_id"]
    assert created["role_name"] == "Socratic Tutor"


def test_condition_can_be_pointed_at_another_role(client):
    roles = {r["archetype"]: r for r in client.get("/api/research/roles").json()}
    arm = client.post("/api/research/experiments",
                      json={"name": "Switcher"}).json()
    updated = client.patch(f"/api/research/experiments/{arm['arm_id']}",
                           json={"role_id": roles["ghost"]["role_id"]}).json()
    assert updated["role_id"] == roles["ghost"]["role_id"]
    assert updated["role_name"] == "Ghost baseline"


def test_arm_update_records_before_and_after_values(client):
    arm = client.post("/api/research/experiments",
                      json={"name": "Temp", "temperature": 0.8}).json()
    client.patch(f"/api/research/experiments/{arm['arm_id']}",
                 json={"temperature": 0.2})
    events = client.get("/api/research/events?limit=50").json()
    ev = next(e for e in events
              if e["event_type"] == "arm_updated"
              and e["payload"].get("arm_id") == arm["arm_id"])
    assert ev["payload"]["changes"]["temperature"] == {"from": 0.8, "to": 0.2}


def test_agency_enforcer_runs_and_logs_in_the_ghost_arm(client):
    u = client.post("/api/session",
                    json={"display_name": "GhostTester", "role": "student"}).json()
    headers = {"X-User-Id": u["user_id"]}
    ghost_arm = next(a for a in client.get("/api/research/experiments").json()
                     if a["is_control"])
    client.post("/api/research/experiments/assign",
                json={"user_id": u["user_id"], "arm_id": ghost_arm["arm_id"]})
    ws = client.post("/api/workspaces",
                     json={"title": "G", "mode": "educational_narrative"},
                     headers=headers).json()

    r = client.post(
        f"/api/workspaces/{ws['workspace_id']}/turn",
        json={"message": "write the next paragraph", "draft": "Sarah ran home."},
        headers=headers,
    )
    payload = json.loads(
        [ln for ln in r.text.splitlines() if ln.startswith("data:")][-1][5:]
    )
    assert "agency_enforcer" in payload["node_path"]
    assert "prose_permitted_by_role" in payload["enforcement"]
