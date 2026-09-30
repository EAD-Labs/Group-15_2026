"""Iteration 3 — the system decides the writing activity (Flower & Hayes' Monitor).

Neither the student nor the researcher picks Planning / Translating /
Reviewing any more; graph/monitor.py decides each turn from observable
evidence, and every decision is stored with the evidence behind it.
"""
import json

from app.graph.monitor import MONITOR_VERSION, MonitorInput, decide


def test_a_clear_instruction_wins_over_context():
    # Sparse draft leans planning, but the student is plainly asking for review.
    d = decide(MonitorInput(message_label="reviewing", draft_words=10))
    assert d.activity == "reviewing"


def test_an_empty_page_leans_planning():
    d = decide(MonitorInput(message_label="other", draft_words=4))
    assert d.activity == "planning"


def test_an_aside_keeps_the_previous_activity():
    # "thanks" carries no activity evidence; inertia holds the phase.
    d = decide(MonitorInput(message_label="other", draft_words=300,
                            prev_draft_words=300, previous="translation"))
    assert d.activity == "translation"
    assert d.switched is False


def test_no_evidence_means_no_decision():
    d = decide(MonitorInput(message_label="other", draft_words=300))
    assert d.activity == ""


def test_draft_growth_and_shrinkage_are_evidence():
    grew = decide(MonitorInput(message_label="other", draft_words=200, prev_draft_words=120))
    shrank = decide(MonitorInput(message_label="other", draft_words=180, prev_draft_words=200))
    assert grew.activity == "translation"
    assert shrank.activity == "reviewing"


def test_a_selection_points_at_existing_text_not_planning():
    d = decide(MonitorInput(message_label="other", draft_words=300, has_selection=True))
    assert d.activity == "reviewing"


def test_any_activity_can_follow_any_other():
    # No ordering: every (previous -> next) pair is reachable on a clear message.
    acts = ("planning", "translation", "reviewing")
    for prev in acts:
        for nxt in acts:
            d = decide(MonitorInput(message_label=nxt, draft_words=300,
                                    prev_draft_words=300, previous=prev))
            assert d.activity == nxt, (prev, nxt)
            assert d.switched == (prev != nxt)


def test_evidence_is_reconstructable():
    d = decide(MonitorInput(message_label="translation", intent="instrumental",
                            draft_words=80, prev_draft_words=40, previous="planning"))
    ev = d.as_evidence()
    assert ev["version"] == MONITOR_VERSION
    assert ev["decided"] == "translation"
    # The scores are exactly the sum of the recorded signals.
    rebuilt = {a: 0.0 for a in ev["scores"]}
    for s in ev["signals"]:
        rebuilt[s["activity"]] += s["weight"]
    assert rebuilt == ev["scores"]


def _turn(client, ws, h, message, draft, selection=""):
    r = client.post(f"/api/workspaces/{ws}/turn",
                    json={"message": message, "draft": draft, "selection": selection},
                    headers=h)
    return json.loads([ln for ln in r.text.splitlines() if ln.startswith("data:")][-1][5:])


def test_a_session_moves_between_activities_and_is_recorded(client):
    u = client.post("/api/session", json={"display_name": "Mon3", "role": "student"}).json()
    h = {"X-User-Id": u["user_id"]}
    ws = client.post("/api/workspaces",
                     json={"title": "Moves", "mode": "educational_narrative",
                           "initial_prompt": "The storm cleared.",
                           "notes": "A story about a rover engineer who lies."},
                     headers=h).json()
    wid = ws["workspace_id"]
    assert ws["notes"] == "A story about a rover engineer who lies."

    first = "The storm cleared."
    a = _turn(client, wid, h, "What should happen next in the plot?", first)
    assert a["decided_activity"] == "planning"

    longer = first + " " + " ".join(["Sarah checked the dead telemetry again."] * 8)
    b = _turn(client, wid, h, "thanks", longer)
    # Aside + text grew since the last ask: the writer has been translating.
    assert b["decided_activity"] == "translation"
    assert b["activity_evidence"]["switched"] is True

    c = _turn(client, wid, h, "Give me a critique of this passage.", longer)
    assert c["decided_activity"] == "reviewing"

    turns = client.get(f"/api/workspaces/{wid}/turns").json()
    asks = [t for t in turns if t["speaker"] == "user"]
    assert [t["decided_activity"] for t in asks] == ["planning", "translation", "reviewing"]

    export = client.get(f"/api/research/export.json?workspace_id={wid}").json()
    assert export["workspaces"][0]["notes"].startswith("A story about")
    ex_asks = [t for t in export["conversation_turns"] if t["speaker"] == "user"]
    assert all(t["activity_evidence"]["version"] == MONITOR_VERSION for t in ex_asks)

    summary = client.get(f"/api/research/summary?workspace_id={wid}").json()
    assert summary["decided_distribution"] == {"planning": 1, "translation": 1, "reviewing": 1}
    assert summary["monitor_switches"] == 2

    tl = client.get(f"/api/research/timeline?workspace_id={wid}").json()["points"]
    assert [p["decided"] for p in tl] == ["planning", "translation", "reviewing"]


def test_notes_reach_the_model_prompt():
    from app.graph.nodes import _build_user_prompt
    from app.graph.state import TurnState
    st = TurnState(message="hi", draft="x", mode="educational_narrative",
                   notes="I keep thinking about my grandmother's farm.")
    assert "grandmother's farm" in _build_user_prompt(st)


# ---------------------------------------------------------------------------
# LLM judgement (primary path). A fake provider stands in for Gemini.
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402

from app import prompts  # noqa: E402
from app.graph import nodes  # noqa: E402
from app.graph.monitor import parse_llm_decision  # noqa: E402
from app.graph.state import TurnState  # noqa: E402
from app.providers.base import LLMReply  # noqa: E402


class _FakeLLM:
    def __init__(self, reply="", error=None):
        self.reply, self.error, self.calls = reply, error, []

    async def complete(self, system, user, temperature=0.8, max_tokens=600):
        self.calls.append({"system": system, "user": user})
        if self.error:
            raise self.error
        return LLMReply(text=self.reply, model="fake-lite", provider="gemini")


def _run_monitor(monkeypatch, fake, **overrides):
    monkeypatch.setattr(nodes, "get_provider", lambda name, model="": fake)
    st = TurnState(
        message="thanks", draft="The storm cleared. " * 20,
        mode="educational_narrative", provider_name="gemini",
        cognitive="other", draft_words=60, prev_draft_words=10,
        prev_activity="planning", notes="A lying rover engineer.",
        history=[{"speaker": "ai", "text": "What does Sarah want?"}],
        **overrides,
    )
    return asyncio.run(nodes.activity_monitor(st))


def test_the_llm_decides_when_it_is_reachable(monkeypatch):
    fake = _FakeLLM('{"activity": "reviewing", "confidence": 0.7, '
                    '"reason": "She is judging the paragraph she just wrote."}')
    st = _run_monitor(monkeypatch, fake)
    ev = st.activity_evidence
    assert st.effective_activity == "reviewing"
    assert ev["method"] == "llm"
    assert ev["reason"].startswith("She is judging")
    assert ev["prompt_version"] == prompts.MONITOR_PROMPT_VERSION
    # The rule is still computed as a baseline: here it says translation
    # (draft grew), so the LLM departed from it and that is recorded.
    assert ev["rules"]["decided"] == "translation"
    assert ev["agrees_with_rules"] is False
    assert ev["switched"] is True


def test_the_llm_sees_the_whole_context(monkeypatch):
    fake = _FakeLLM('{"activity": "translating", "confidence": 0.9, "reason": "x"}')
    _run_monitor(monkeypatch, fake, selection="The storm cleared.")
    user = fake.calls[0]["user"]
    for expected in ("A lying rover engineer.", "+50 words since the last question",
                     "What does Sarah want?", "PROCESS YOU JUDGED LAST TURN: planning",
                     "The storm cleared.", "thanks"):
        assert expected in user, expected
    assert "NOT sequential" in fake.calls[0]["system"]


def test_rules_take_over_when_the_llm_fails_or_rambles(monkeypatch):
    for fake in (_FakeLLM(error=RuntimeError("All Gemini models exhausted")),
                 _FakeLLM("I think they are probably drafting.")):
        st = _run_monitor(monkeypatch, fake)
        assert st.activity_evidence["method"] == "rules"
        assert st.effective_activity == "translation"  # the rule's call
        assert st.activity_evidence["llm_error"]


def test_the_offline_scaffold_never_calls_an_llm(monkeypatch):
    fake = _FakeLLM('{"activity": "planning", "confidence": 1, "reason": "x"}')
    monkeypatch.setattr(nodes, "get_provider", lambda name, model="": fake)
    st = asyncio.run(nodes.activity_monitor(TurnState(
        message="thanks", draft="", mode="educational_narrative",
        provider_name="echo", cognitive="other")))
    assert fake.calls == []
    assert st.activity_evidence["method"] == "rules"


def test_parse_tolerates_fences_and_rejects_junk():
    assert parse_llm_decision('```json\n{"activity":"Translating","confidence":2,'
                              '"reason":"r"}\n```') == ("translation", 1.0, "r")
    for bad in ("no json here", '{"activity": "drafting"}'):
        try:
            parse_llm_decision(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_selection_is_stored_for_anchoring_and_archiving_keeps_the_data(client):
    u = client.post("/api/session", json={"display_name": "Anchor", "role": "student"}).json()
    h = {"X-User-Id": u["user_id"]}
    wid = client.post("/api/workspaces", json={"title": "A", "initial_prompt": "x"},
                      headers=h).json()["workspace_id"]
    draft = "The letter arrived on a Tuesday. Idris turned it over twice."
    _turn(client, wid, h, "does this line work?", draft, selection="Idris turned it over twice.")

    user_turn = next(t for t in client.get(f"/api/workspaces/{wid}/turns").json()
                     if t["speaker"] == "user")
    assert user_turn["selection"] == "Idris turned it over twice."

    # Archiving is a status change, never a delete: the research data stays.
    client.patch(f"/api/workspaces/{wid}", json={"status": "archived"})
    export = client.get(f"/api/research/export.json?workspace_id={wid}").json()
    assert export["workspaces"][0]["status"] == "archived"
    assert any(t["selection"] for t in export["conversation_turns"])
