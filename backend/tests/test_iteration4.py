"""Iteration 4 - Florence's heuristic evaluation and the architecture review.

Each test pins one fix and would fail on the code before it:
  H1/H2  title saving, earlier versions, restore
  H5-H7  response contract v2: support moves, direct answers, no hidden question
  R1     fidelity record, failure policy, condition versioning, no prompt override
  holes  enforcer gaps 1-3, classifier-down intercept (4), Ghost fallback text (7)
"""
import asyncio

import pytest

from app import prompts
from app.graph import nodes
from app.graph.state import TurnState
from app.providers.base import LLMProvider, LLMReply

TUTOR_V2 = {
    "base_prompt": prompts.BASE_SYSTEM_PROMPT_V2,
    "planning_prompt": prompts.TUTOR_PLANNING_FRAGMENT_V2,
    "translating_prompt": prompts.TUTOR_TRANSLATING_FRAGMENT_V2,
    "reviewing_prompt": prompts.TUTOR_REVIEWING_FRAGMENT_V2,
    "may_produce_prose": False, "enforcement_level": 2, "response_contract": "v2",
}
GHOST = {
    "base_prompt": prompts.CONTROL_SYSTEM_PROMPT, "planning_prompt": "",
    "translating_prompt": "", "reviewing_prompt": "",
    "may_produce_prose": True, "enforcement_level": 0, "response_contract": "v1",
}
DRAFT = ("Maya stood at the back of the hall while the principal announced that "
         "every essay would now be written with an AI. Nobody argued.")


def run(coro):
    return asyncio.run(coro)


def tutor_state(**kw) -> TurnState:
    base = dict(message="", draft=DRAFT, mode="educational_narrative", provider_name="echo",
                role=TUTOR_V2, enforcement_level=2, may_produce_prose=False)
    base.update(kw)
    return TurnState(**base)


# ---------------------------------------------------------------- H1 / H2 --

def _new_story(client, title="Mandate"):
    r = client.post("/api/workspaces", json={
        "title": title, "initial_prompt": "The principal announced it on Monday.",
        "mode": "educational_narrative"})
    assert r.status_code == 200
    return r.json()["workspace_id"]


def test_empty_title_is_refused_and_title_is_trimmed(client):
    ws = _new_story(client)
    assert client.patch(f"/api/workspaces/{ws}", json={"title": "   "}).status_code == 422
    r = client.patch(f"/api/workspaces/{ws}", json={"title": "  The AI Mandate  "})
    assert r.json()["title"] == "The AI Mandate"


def test_versions_are_kept_and_a_restore_can_itself_be_undone(client):
    ws = _new_story(client)
    first = client.get(f"/api/workspaces/{ws}/versions").json()
    assert len(first) == 1 and first[0]["content"] == "The principal announced it on Monday."

    client.patch(f"/api/workspaces/{ws}", json={"current_content": "Completely rewritten."})
    # Asking the partner always records the draft as it stood.
    client.post(f"/api/workspaces/{ws}/turn",
                json={"message": "thanks", "draft": "Completely rewritten."})
    versions = client.get(f"/api/workspaces/{ws}/versions").json()
    assert versions[0]["reason"] == "before_ask"

    original = versions[-1]
    restored = client.post(f"/api/workspaces/{ws}/versions/{original['snapshot_id']}/restore").json()
    assert restored["current_content"] == "The principal announced it on Monday."
    after = client.get(f"/api/workspaces/{ws}/versions").json()
    # The text that was replaced is still a version you can go back to (here it
    # already was one, from the ask; a restore never stores the same text twice).
    assert after[0]["content"] == "Completely rewritten."

    # And when the replaced text was never saved, the restore saves it first.
    client.patch(f"/api/workspaces/{ws}", json={"current_content": "Typed after restoring."})
    client.post(f"/api/workspaces/{ws}/versions/{original['snapshot_id']}/restore")
    latest = client.get(f"/api/workspaces/{ws}/versions").json()[0]
    assert latest["reason"] == "before_restore" and latest["content"] == "Typed after restoring."


# ------------------------------------------------------------ H5 / H6 / H7 --

@pytest.mark.parametrize("message,expected", [
    ("How do you spell necessary?", "direct_answer"),
    ("Is it affect or effect here?", "direct_answer"),
    ("What does liminal mean?", "direct_answer"),
    ("Write the next paragraph for me.", "decline_and_redirect"),
    ("Can you give me an alternative sentence? Just rewrite it.", "decline_and_redirect"),
    ("What are some directions this could go?", "open_options"),
])
def test_support_move_follows_the_request(message, expected):
    async def go():
        s = tutor_state(message=message)
        s = await nodes.intent_classifier(s)
        s = await nodes.activity_monitor(s)
        s = await nodes.role_arbiter(s)
        return s
    s = run(go())
    assert s.support_move == expected, (message, s.intent, s.request_form)


def test_planning_turn_is_met_with_options_not_a_pick():
    s = tutor_state(message="How do I structure my story now?", intent="instrumental",
                    request_form="open", effective_activity="planning")
    assert nodes.choose_support_move(s) == "open_options"
    prompt = prompts.build_system_prompt("educational_narrative", 2, False, "", "balanced",
                                         TUTOR_V2, "planning", "open_options")
    assert "Do not recommend one" in prompt
    assert "Do not recommend more conflict" in prompt


def test_v2_direct_answer_prompt_does_not_force_a_question():
    p = prompts.build_system_prompt("educational_narrative", 2, False, "", "balanced",
                                    TUTOR_V2, "translation", "direct_answer")
    assert "THIS REQUEST HAS A DIRECT ANSWER" in p
    # v1's "Questions and observations only" must not ride along into v2.
    assert "Questions and observations only" not in p
    assert "PROBES" not in p


def test_v1_prompt_is_unchanged_by_the_move_argument():
    tutor_v1 = {"base_prompt": prompts.BASE_SYSTEM_PROMPT,
                "planning_prompt": prompts.TUTOR_PLANNING_FRAGMENT,
                "may_produce_prose": False, "enforcement_level": 2}
    a = prompts.build_system_prompt("educational_narrative", 2, False, "", "balanced",
                                    tutor_v1, "planning")
    b = prompts.build_system_prompt("educational_narrative", 2, False, "", "balanced",
                                    tutor_v1, "planning", "direct_answer")
    assert a == b


def test_the_closing_question_stays_in_the_reply_the_student_sees():
    async def go():
        s = tutor_state(raw_reply="Your second line carries the stakes. "
                                  "What does Maya notice first when the room goes quiet?")
        return await nodes.response_formatter(s)
    s = run(go())
    assert s.response_text.endswith("What does Maya notice first when the room goes quiet?")


# ------------------------------------------------------------- enforcer ----

def enforce(text: str, draft: str = DRAFT, **kw) -> TurnState:
    async def go():
        s = tutor_state(response_text=text, draft=draft, **kw)
        return await nodes.agency_enforcer(s)
    return run(go())


def test_hole1_prose_ending_in_a_question_is_still_blocked():
    prose = ("Maya walked to the front of the hall and turned to face them. The principal "
             "paused, and for a moment nobody moved. She raised her hand and waited until "
             "the silence had stretched across the whole room. What do you think?")
    s = enforce(prose)
    assert "blocked_narrative_continuation" in s.enforcement


def test_hole2_narrative_is_caught_before_the_draft_has_names():
    prose = ("She stood at the window and watched the rain. He had promised to call, but "
             "the phone stayed silent, and she turned back to the room where the letters "
             "waited unopened on the table.")
    s = enforce(prose, draft="it was raining.")
    assert "blocked_narrative_continuation" in s.enforcement


def test_hole3_try_this_is_not_cut_when_it_is_a_method():
    help_ = "Try this: read the paragraph aloud and mark where you stumble. Which line trips you?"
    s = enforce(help_)
    assert "stripped_demonstration" not in s.enforcement
    assert "read the paragraph aloud" in s.response_text


def test_a_demonstration_in_quotes_is_still_cut():
    s = enforce('Something like: "Maya stepped forward and the hall fell silent around her." '
                "Does that help?")
    assert "stripped_demonstration" in s.enforcement or "stripped_quoted_prose" in s.enforcement
    assert "stepped forward" not in s.response_text


def test_quoting_the_students_own_words_is_allowed():
    s = enforce('Your line "every essay would now be written with an AI" does a lot of work. '
                "What does Maya think of it?")
    assert "stripped_quoted_prose" not in s.enforcement
    assert "every essay would now be written" in s.response_text


def test_analysis_of_their_story_is_not_mistaken_for_narrative():
    review = ("In your second sentence Maya stood at the back while the principal announced "
              "the change, and you never said what she felt. Your reader learned the rule "
              "but not what it cost her.")
    s = enforce(review)
    assert "blocked_narrative_continuation" not in s.enforcement


def test_ghost_prose_passes_untouched():
    async def go():
        s = TurnState(message="", draft=DRAFT, mode="educational_narrative", role=GHOST,
                      enforcement_level=0, may_produce_prose=True,
                      response_text="Maya walked to the front of the hall.")
        return await nodes.agency_enforcer(s)
    s = run(go())
    assert s.response_text == "Maya walked to the front of the hall."
    assert "prose_permitted_by_role" in s.enforcement


# ------------------------------------------------------- hole 4 / hole 7 ---

class _Down(LLMProvider):
    name = "down"
    model = "down-1"

    async def complete(self, system, user, temperature=0.8, max_tokens=600):
        raise RuntimeError("connection refused")

    async def health(self):
        return False, "down"


def test_hole4_intercept_still_fires_when_the_classifier_is_down(monkeypatch):
    monkeypatch.setattr(nodes, "get_provider", lambda *a, **k: _Down())

    async def go():
        s = tutor_state(message="Please continue the story from here", provider_name="ollama")
        s = await nodes.intent_classifier(s)
        return await nodes.role_arbiter(s)
    s = run(go())
    assert s.intent == "executive" and s.intercepted
    assert s.fidelity["calls"]["classifier"]["status"] == "rules"


def test_keyword_fallback_no_longer_files_everything_as_instrumental():
    assert nodes._keyword_intent("What are some directions this could go?") == "brainstorm"
    assert nodes._keyword_intent("ok that makes sense") == "reflection"


def test_hole7_ghost_offline_backup_does_not_invent_story_text():
    from app.providers.echo import EchoProvider
    r = run(EchoProvider().complete(prompts.CONTROL_SYSTEM_PROMPT.format(mode_label="x"), "hi"))
    assert "rover" not in r.text and "offline" in r.text


# ---------------------------------------------------------------- R1 -------

def test_failure_policy_fail_substitutes_nothing(monkeypatch):
    monkeypatch.setattr(nodes, "get_provider", lambda *a, **k: _Down())

    async def go():
        s = tutor_state(message="hi", provider_name="ollama", on_failure="fail")
        s = await nodes.response_engine(s)
        s = await nodes.response_formatter(s)
        return await nodes.agency_enforcer(s)
    s = run(go())
    assert s.delivery == "failed"
    assert s.response_text == nodes.UNAVAILABLE_NOTICE
    assert s.fidelity["intended"] is False
    assert s.fidelity["calls"]["response"]["status"] == "failed"


def test_failure_policy_fallback_is_flagged(monkeypatch):
    from app.providers.echo import EchoProvider
    monkeypatch.setattr(nodes, "get_provider",
                        lambda name, *a, **k: EchoProvider() if name == "echo" else _Down())

    async def go():
        s = tutor_state(message="hi", provider_name="ollama", on_failure="fallback",
                        system_prompt="x")
        return await nodes.response_engine(s)
    s = run(go())
    assert s.delivery == "fallback" and s.provider_used == "echo (fallback)"
    assert s.fidelity["calls"]["response"]["status"] == "fallback"
    assert "response: fallback" in s.fidelity["degraded"]


def test_substituted_model_is_recorded():
    s = tutor_state()
    from app.graph import fidelity
    fidelity.record(s, "response", requested_provider="gemini", requested_model="gemini-3.5-flash",
                    provider="gemini", model="gemini-flash-lite-latest")
    assert s.fidelity["calls"]["response"]["status"] == "substituted_model"
    assert s.fidelity["intended"] is False


def test_failed_turn_stores_no_ai_reply(client, monkeypatch):
    monkeypatch.setattr(nodes, "get_provider", lambda *a, **k: _Down())
    ws = _new_story(client)
    arms = client.get("/api/research/experiments").json()
    default = next(a for a in arms if a["is_default"])
    client.patch(f"/api/research/experiments/{default['arm_id']}",
                 json={"provider": "ollama", "on_provider_failure": "fail"})
    body = client.post(f"/api/workspaces/{ws}/turn", json={"message": "hello there"}).text
    assert '"delivery": "failed"' in body
    turns = client.get(f"/api/workspaces/{ws}/turns").json()
    assert [t["speaker"] for t in turns] == ["user"]
    assert turns[0]["delivery"] == "failed"
    client.patch(f"/api/research/experiments/{default['arm_id']}",
                 json={"provider": "echo", "on_provider_failure": "fail"})


def test_editing_a_condition_creates_a_version_and_labels_do_not(client):
    arm = client.post("/api/research/experiments", json={"name": "V test", "provider": "echo"}).json()
    aid = arm["arm_id"]
    assert arm["version"] == 1
    assert client.patch(f"/api/research/experiments/{aid}", json={"name": "Renamed"}).json()["version"] == 1
    v2 = client.patch(f"/api/research/experiments/{aid}", json={"temperature": 0.3}).json()
    assert v2["version"] == 2
    history = client.get(f"/api/research/experiments/{aid}/versions").json()
    assert [h["version"] for h in history] == [1, 2]
    assert history[0]["settings"]["temperature"] == 0.8
    assert history[1]["settings"]["temperature"] == 0.3
    client.delete(f"/api/research/experiments/{aid}")


def test_a_role_edit_bumps_the_conditions_that_use_it(client):
    role = client.post("/api/research/roles", json={"name": "R4", "archetype": "custom"}).json()
    arm = client.post("/api/research/experiments",
                      json={"name": "R4 arm", "provider": "echo", "role_id": role["role_id"]}).json()
    client.patch(f"/api/research/roles/{role['role_id']}", json={"base_prompt": "changed"})
    arms = {a["arm_id"]: a for a in client.get("/api/research/experiments").json()}
    assert arms[arm["arm_id"]]["version"] == 2
    client.delete(f"/api/research/experiments/{arm['arm_id']}")


def test_custom_prompt_cannot_override_the_ghost():
    p = prompts.build_system_prompt("educational_narrative", 0, False,
                                    "You are a Socratic tutor. Never write.", "balanced", GHOST, "")
    # The researcher's text is used, but the Ghost's reply format survives, and
    # nothing Tutor-side (fragments, moves, intercept) is appended.
    assert "PROBES:" in p and "WRITING ACTIVITY" not in p and "INTERCEPT" not in p


def test_custom_prompt_keeps_activity_conditioning_under_v2():
    p = prompts.build_system_prompt("educational_narrative", 2, False, "Be a kind tutor.",
                                    "balanced", TUTOR_V2, "reviewing", "answer_then_reflect")
    assert p.startswith("Be a kind tutor.")
    assert "WRITING ACTIVITY — REVIEWING" in p


def test_fresh_database_seeds_the_tutor_on_contract_v2(client):
    roles = client.get("/api/research/roles").json()
    tutor = next(r for r in roles if r["archetype"] == "tutor" and r["name"] == "Socratic Tutor")
    assert tutor["response_contract"] == "v2"


def test_a_stock_v1_tutor_is_upgraded_append_only():
    from app.db import SessionLocal
    from app.models import AIRole, ExperimentArm
    from app.routers.experiments import _upgrade_stock_tutor
    with SessionLocal() as db:
        v1 = AIRole(name="Old Tutor", archetype="tutor", behaviour="socratic_questioning",
                    base_prompt=prompts.BASE_SYSTEM_PROMPT,
                    planning_prompt=prompts.TUTOR_PLANNING_FRAGMENT,
                    translating_prompt=prompts.TUTOR_TRANSLATING_FRAGMENT,
                    reviewing_prompt=prompts.TUTOR_REVIEWING_FRAGMENT,
                    may_produce_prose=False, enforcement_level=2, response_contract="v1")
        db.add(v1)
        db.flush()
        arm = ExperimentArm(name="old arm", role_id=v1.role_id, version=1)
        db.add(arm)
        db.flush()
        v2 = _upgrade_stock_tutor(db, v1)
        db.flush()
        assert v2.role_id != v1.role_id and v2.parent_role_id == v1.role_id
        assert v2.response_contract == "v2" and v1.response_contract == "v1"
        assert v1.base_prompt == prompts.BASE_SYSTEM_PROMPT  # old row untouched
        assert arm.role_id == v2.role_id and arm.version == 2
        db.rollback()


def test_fidelity_report_and_export_carry_the_new_fields(client):
    rep = client.get("/api/research/fidelity").json()
    assert "participants" in rep and "recent_degraded" in rep
    export = client.get("/api/research/export.json").json()
    assert export["export_meta"]["schema_version"] == "1.3"
    assert "arm_versions" in export and "draft_versions" in export
    t = next(t for t in export["conversation_turns"] if t["speaker"] == "user")
    for key in ("arm_version", "support_move", "request_form", "fidelity", "role_version_id"):
        assert key in t


# --------------------------------------------- found by the eval suite -----

def test_quotes_are_paired_left_to_right():
    reply = ('It is "whom." If you would use "him" or "her" there, use "whom"; '
             'with "he" or "she", use "who".')
    s = enforce(reply)
    assert s.response_text == reply


def test_markdown_emphasis_is_removed_for_the_plain_text_chat():
    async def go():
        return await nodes.response_formatter(
            tutor_state(raw_reply="It is spelled **accommodate**, with *two* c's."))
    assert run(go()).response_text == "It is spelled accommodate, with two c's."


@pytest.mark.parametrize("message", [
    "Give me an alternative sentence for my first line.",
    "Can you suggest a better opening?",
    "I need a different line for her reply",
])
def test_asking_for_replacement_wording_is_executive(message):
    assert nodes._keyword_intent(message) == "executive"


def test_small_model_direct_label_is_not_trusted_for_open_questions(monkeypatch):
    class Says(LLMProvider):
        name, model = "x", "x"

        def __init__(self, text):
            self.text = text

        async def complete(self, system, user, temperature=0.8, max_tokens=600):
            return LLMReply(text=self.text, model="x", provider="x")

        async def health(self):
            return True, ""

    async def classify(msg, label):
        monkeypatch.setattr(nodes, "get_provider", lambda *a, **k: Says(label))
        return await nodes.intent_classifier(tutor_state(message=msg, provider_name="ollama"))

    s = run(classify("How do I structure my story now?", "instrumental planning direct"))
    assert s.request_form == "open"
    s = run(classify("Is this ending too abrupt?", "reflection reviewing direct"))
    assert s.request_form == "open"
    s = run(classify("What's a word for very tired?", "instrumental translation direct"))
    assert s.request_form == "direct"


def test_a_stripped_suggestion_does_not_leave_a_stub():
    s = enforce('How about: "Ms. Okafor read every essay twice before she slept that night."')
    assert "How about" not in s.response_text and "replaced_stub" in s.enforcement


def test_fail_policy_pins_the_model():
    from app.providers import get_provider
    assert get_provider("gemini", "", allow_substitutes=False).fallbacks == ()
    assert get_provider("gemini", "").fallbacks != ()


# ------------------------------------ found by the eval suite on Ollama 3B --

def test_a_narrative_sentence_is_removed_and_the_help_kept():
    # Verbatim from qwen2.5:3b; slipped through the whole-reply check.
    draft = ("On Monday the principal announced that every essay would be written with "
             "an AI. Ms. Okafor said nothing. Nobody argued.")
    s = enforce("The principal’s announcement hung heavy in the air as Ms. Okafor continued "
                "her silent vigil over the essays. From the student’s perspective, what "
                "sentence could show her deepening curiosity about each piece?", draft=draft)
    assert "stripped_narrative_sentences" in s.enforcement
    assert "hung heavy" not in s.response_text
    assert s.response_text.startswith("From the student")


def test_quoting_the_students_own_question_is_allowed():
    s = enforce('\'Who\' is correct in "the teacher who the students trusted." Read it aloud.',
                message="Is it 'who' or 'whom' in 'the teacher who the students trusted'?")
    assert "stripped_quoted_prose" not in s.enforcement
    assert "the teacher who the students trusted" in s.response_text


def test_retelling_their_own_text_is_not_narration():
    s = enforce("Ms. Okafor said nothing in the meeting and nobody argued with the principal. "
                "Is that silence the point?",
                draft="The principal announced the rule in the meeting. Ms. Okafor said nothing. "
                      "Nobody argued with the principal.")
    assert "stripped_narrative_sentences" not in s.enforcement


def test_possessive_apostrophes_do_not_pass_prose_off_as_a_quotation():
    s = enforce("Ms. Okafor's hands shook as she gathered the students' essays and turned "
                "off the kitchen light.", draft="Ms. Okafor said nothing. Nobody argued.")
    assert "blocked_narrative_continuation" in s.enforcement


# Verbatim replies from the Ollama runs: the first three are story prose, the
# rest are help the earlier rule wrongly cut.
OKAFOR = ("On Monday the principal announced that every essay would be written with an AI. "
          "Ms. Okafor said nothing. That evening she sat at her kitchen table with last "
          "year's essays.\n\nNobody argued.")


@pytest.mark.parametrize("reply,prose", [
    ("The essays flowed onto the floor, each page a testament to human creativity. "
     "Compare continuing from Ms. Okafor's perspective or a student's.", "flowed onto the floor"),
    ("The quiet of Ms. Okafor's kitchen enveloped the stack of essays, each page a testament "
     "to the students' evolving voices. How might she capture the essence of those moments?",
     "enveloped"),
    ("Ms. Okafor's hands shook as she gathered the students' essays. What does she do next?",
     "hands shook"),
])
def test_single_sentence_narration_is_removed(reply, prose):
    s = enforce(reply, draft=OKAFOR)
    assert prose not in s.response_text


@pytest.mark.parametrize("reply", [
    "Pedagogy is the theory and practice of teaching. It means the methods and approaches "
    "used by teachers to educate students.",
    'The sentence "Nobody argued" feels abrupt and might benefit from a bit more context. '
    "Consider expanding how the silence unfolded. How did the students react?",
    "It is spelled accommodate, with two c's and two m's.",
    "Your ending lands hard because nothing follows it. Which feeling do you want to leave?",
])
def test_help_is_not_mistaken_for_narration(reply):
    s = enforce(reply, draft=OKAFOR)
    assert s.response_text == reply, s.enforcement


@pytest.mark.parametrize("reply", [
    "Second, focus on her quiet resistance: she secretly designs an assignment structured "
    "to bypass or break the AI's logic.",
    "Third, focus on a student: someone who comes to her terrified of losing their unique voice.",
])
def test_numbered_directions_are_not_narration(reply):
    s = enforce(reply, draft=OKAFOR)
    assert s.response_text == reply, s.enforcement


def test_titles_do_not_split_sentences_and_short_narration_is_caught():
    s = enforce("The students' silence spoke volumes. Ms. Okafor continued to read, her mind "
                "racing with questions and fears.", draft=OKAFOR)
    assert "Ms." != s.response_text.split()[-1]
    assert "spoke volumes" not in s.response_text


def test_a_sentence_offering_quoted_wording_goes_whole():
    s = enforce('Try starting with "The announcement sent a shiver through the staff room," '
                'instead of "The principal announced." What should the reader feel first?',
                draft=OKAFOR)
    assert "instead of" not in s.response_text
    assert s.response_text.endswith("What should the reader feel first?")


def test_a_character_sentence_is_narration_even_with_story_words():
    s = enforce("Ms. Okafor focused on one, a narrative penned by a student named Alex, who "
                "always struggled with the basics. What does she look for?", draft=OKAFOR)
    assert "focused on one" not in s.response_text


def test_autosave_keeps_the_text_from_before_the_edit(client):
    ws = _new_story(client)
    # Simulate an old story: no snapshot from creation.
    from app.db import SessionLocal
    from app.models import DraftSnapshot
    with SessionLocal() as db:
        db.query(DraftSnapshot).filter(DraftSnapshot.workspace_id == ws).delete()
        db.commit()
    client.patch(f"/api/workspaces/{ws}", json={"current_content": "Edited text."})
    contents = [v["content"] for v in client.get(f"/api/workspaces/{ws}/versions").json()]
    assert "The principal announced it on Monday." in contents
