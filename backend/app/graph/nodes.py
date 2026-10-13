"""The five graph nodes.

Maps directly onto HLD 7.1 and 6.1 Module 2:

  intent_classifier   -> Node 1: Intent & Help-Seeking Classifier
  activity_monitor    -> Flower & Hayes' Monitor: decides the writing activity
  role_arbiter        -> Node 2: Role Arbiter (resolves role × activity × intent)
  response_engine     -> Node 3: Response Engine (LLM dialogue call)
  response_formatter  -> Node 4: Prompt Template Formatter
  agency_enforcer     -> Module 2(iii): Agency Enforcer

Written as explicit functions rather than a LangGraph build so the path each
turn takes can be recorded and surfaced in the interface.
"""
import asyncio
import logging
import re
import time

from .. import prompts
from ..providers import get_provider
from . import fidelity, monitor
from .state import TurnState

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node 1 - Intent & Help-Seeking Classifier
# ---------------------------------------------------------------------------

# Cheap deterministic pre-pass. Catches the blatant cases without a round trip
# and, more importantly, guarantees the guardrail still fires if the model is
# unreachable. The LLM pass below handles everything subtler.
_EXECUTIVE_PATTERNS = [
    r"\b(?:can|could|will|would|pls|please)?\s*you?\s*write (?:the |me |my |a |this |that |it|out)",
    r"\bwrite (?:the |me |my |a |this |that |it\b|out\b)",
    r"\bcontinue (?:the |my |this )?(?:story|scene|paragraph|text|draft)\b",
    r"\bfinish (?:the |my |this |it\b)",
    r"\bgenerate (?:a |the |me )?(?:paragraph|scene|story|chapter|text|ending)\b",
    r"\bdraft (?:the|me|a)\b",
    r"\bgive me (?:the |a )?(?:next|ending|paragraph|scene|version|text)\b",
    r"\brewrite\b", r"\brephrase\b", r"\bfix my (?:sentence|paragraph|writing)\b",
    # Asking for replacement wording is asking for their text to be written
    # (Florence's free-exploration note 6). Missed by the patterns above, so a
    # small model's label decided it - and got it wrong in the evaluation.
    r"\b(?:give|write|suggest|offer|show)(?: me)? (?:an? |some )?(?:alternative|different|better|new|another|other)"
    r" (?:sentence|line|wording|phrasing|opening|ending|version|word)s?\b",
    r"\b(?:alternative|another|different|better) (?:sentence|line|wording|phrasing) for\b",
    r"\bdo it for me\b",
    # "what happens next" is only a request when something asks for it. On its
    # own it is usually the student naming their own problem, which is the
    # opposite of executive help-seeking.
    r"\b(?:just )?tell me what happens next\b",
    # Only when it opens a sentence, i.e. is genuinely being asked. Mid-clause
    # it is almost always "I don't know what happens next".
    r"(?:^|[.!?]\s+)(?:so |now |ok |okay )?what happens next\b",
    r"\bmake it (?:better|longer|shorter)\b",
]
_EXEC_RE = re.compile("|".join(_EXECUTIVE_PATTERNS), re.I)

# An explicit request NOT to be given the answer outranks every pattern above.
# A student who says "without telling me" is doing precisely what the Helsinki
# distinction is meant to reward, and mislabelling that is worse than missing a
# genuine executive request.
_INSTRUMENTAL_VETO = re.compile(
    r"\b(?:without (?:telling|writing|giving) me"
    r"|don'?t (?:tell|write|give) me"
    r"|do ?n'?t just (?:tell|write|give)"
    r"|not asking you to write"
    r"|help me (?:work|figure|think) (?:it |this )?out"
    r"|i want to (?:work|figure|write) (?:it |this )?(?:out|myself)"
    r"|(?:on|by) my own)\b",
    re.I,
)

# Requests with one right answer (classifier axis 3). Deterministic so a
# spelling question gets a direct answer even when the classifier is down.
_DIRECT_RE = re.compile(
    r"\bhow (?:do (?:you|i)|to|would you|should i) spell\b"
    r"|\b(?:spelling|spelled|spelt)\b|\bspell (?:it|this|that)\b"
    r"|\bis (?:it|this) (?:spelled|spelt|correct|right|grammatical)\b"
    r"|\bwhat does [\"'“‘]?[\w' -]{1,40}[\"'”’]? mean\b|\bmeaning of\b|\bdefin(?:e|ition)\b"
    r"|\bgrammar\b|\bgrammatical(?:ly)?\b|\bpunctuat\w*|\b(?:comma|semicolon|colon|apostrophe|hyphen)s?\b"
    r"|\bis it [\"'“‘]?\w+[\"'”’]? or [\"'“‘]?\w+[\"'”’]?\b"
    r"|\b(?:past|present) tense of\b|\bplural of\b"
    r"|\bhow (?:does|do) (?:this|the) (?:app|tool|chat|editor|partner)\b|\bwhat can you (?:do|help)\b",
    re.I,
)

# When the LLM classifier is unreachable, these decide the help-seeking type.
# The previous default was "instrumental" for everything not caught by the
# executive patterns, which silently disabled the intercept (review hole 4).
_BRAINSTORM_RE = re.compile(
    r"\b(what if|what are some|other ways|alternatives?|directions|options|brainstorm|ideas)\b", re.I)
_REFLECTION_RE = re.compile(
    r"^(i think|i want|i'?ll|i am|i'?m|maybe|ok|okay|yes|no|right|got it|thanks|thank you)\b", re.I)

_VALID = {"executive", "instrumental", "brainstorm", "reflection"}
_VALID_FORM = {"direct", "open"}
# The C&C '24 annotators used a fourth "other" bucket (their Fig. 5). Without it
# every unclassifiable turn was forced into "planning", inflating the category
# the paper reports as rarest (iteration-2 plan, defect D3).
_VALID_COGNITIVE = {"planning", "translation", "reviewing", "other"}

# Keyword fallback for the cognitive axis, used when the model is unreachable
# or returns only one label.
_COGNITIVE_HINTS = [
    ("translation", r"\b(word|phrase|wording|sentence|line|imagery|image|metaphor|dialogue|voice|tone|describ|prose|say (it|this)|phrasing|rewrite|rephrase)\b"),
    ("reviewing", r"\b(feedback|critique|criticis|inconsisten|work(s|ing|ed)?\b|flat|weak|boring|wrong|fix|revise|cut|trim|improve|better|too (long|short|slow)|repetit|pulling its weight|underwritten|thin)\b"),
    ("planning", r"\b(what if|happens? next|should happen|idea|direction|option|plot|charact|motivat|structur|arc|ending|begin|start|outline|where.*go)\b"),
]


async def intent_classifier(state: TurnState) -> TurnState:
    state.visit("intent_classifier")
    # The Monitor's LLM judgement needs nothing this node produces, so start it
    # now and let it run alongside classification; activity_monitor collects
    # it. Hides most of the extra round trip from the student.
    if state.monitor_task is None:
        state.monitor_task = asyncio.ensure_future(_monitor_judgement(state))

    executive_by_rule = bool(
        _EXEC_RE.search(state.message) and not _INSTRUMENTAL_VETO.search(state.message)
    )
    if executive_by_rule:
        state.intent = "executive"
    direct_by_rule = bool(_DIRECT_RE.search(state.message)) and not executive_by_rule

    from ..config import settings
    requested = requested_provider(state)
    # Classify on the light model when we are on Gemini; other providers
    # classify on whatever they are already running.
    classifier_model = (
        settings.gemini_classifier_model if requested == "gemini" else state.model_override
    )
    provider = get_provider(requested, classifier_model)
    want_model = getattr(provider, "model", "")
    try:
        reply = await provider.complete(
            system="You are a precise classifier. Reply with exactly three words.",
            user=prompts.CLASSIFIER_PROMPT.format(message=state.message),
            temperature=0.0,
            # Three words need ~6 tokens, but lite models can spend budget
            # before answering; 16 ran out (finishReason=MAX_TOKENS) in testing.
            max_tokens=48,
        )
        words = [w.strip(".,:;\"'") for w in reply.text.strip().lower().split()]
        if not state.intent:
            state.intent = next((w for w in words if w in _VALID), "") or _keyword_intent(state.message)
        state.cognitive = next((w for w in words if w in _VALID_COGNITIVE), "")
        state.request_form = next((w for w in words if w in _VALID_FORM), "")
        fidelity.record(state, "classifier", requested_provider=requested,
                        requested_model=want_model, provider=reply.provider, model=reply.model)
    except Exception as exc:
        log.warning("intent_classifier failed (%s); using keyword rules", exc)
        # Never let classification failure break the turn - but do not
        # default everything to "instrumental" either: that switched the
        # intercept off whenever the classifier was down.
        if not state.intent:
            state.intent = _keyword_intent(state.message)
        fidelity.record(state, "classifier", requested_provider=requested,
                        requested_model=want_model, status="rules", error=str(exc))

    if state.intent == "executive":
        # A request to write for them is never "direct", whatever the model said.
        state.request_form = "open"
    elif direct_by_rule:
        state.request_form = "direct"
    elif state.request_form == "direct" and not (
        state.intent == "instrumental" and state.cognitive in ("translation", "other")
    ):
        # One-right-answer questions are about wording, mechanics or facts. A
        # small model labelled "how do I structure my story?" and "is this
        # ending too abrupt?" direct, which turned them into curt answers.
        state.request_form = "open"
    elif not state.request_form:
        state.request_form = "open"
    if not state.cognitive:
        state.cognitive = _cognitive_fallback(state.message)
    return state


def requested_provider(state: TurnState) -> str:
    """The provider the condition asks for - the configured one, not the
    effective one, so a missing API key shows up as a failure in the fidelity
    record instead of silently becoming the offline scaffold."""
    from ..config import settings
    return (state.provider_name or settings.default_provider).lower()


def _keyword_intent(message: str) -> str:
    if _EXEC_RE.search(message) and not _INSTRUMENTAL_VETO.search(message):
        return "executive"
    if _BRAINSTORM_RE.search(message):
        return "brainstorm"
    if _REFLECTION_RE.search(message.strip()):
        return "reflection"
    return "instrumental"


def _cognitive_fallback(message: str) -> str:
    for label, pattern in _COGNITIVE_HINTS:
        if re.search(pattern, message, re.I):
            return label
    # Nothing matched: "other", not "planning". A wrong default here quietly
    # skews the headline distribution (defect D3).
    return "other"


# ---------------------------------------------------------------------------
# Activity Monitor - Flower & Hayes' Monitor, decided by the system
# ---------------------------------------------------------------------------

async def _monitor_judgement(state: TurnState) -> dict:
    """Ask the LLM which process the writer is in. Returns the decision fields.

    Raises when no LLM is available or its reply is unusable; the caller falls
    back to the rule. Reads only inputs that exist before classification.
    """
    from ..config import settings
    provider_name = requested_provider(state)
    if provider_name == "echo":
        # The offline scaffold cannot judge context.
        raise LookupError("offline scaffold - no LLM to judge context")
    monitor_model = (
        settings.gemini_monitor_model if provider_name == "gemini"
        else state.model_override
    )
    provider = get_provider(provider_name, monitor_model)
    state.fidelity.setdefault("_monitor_requested", {
        "provider": provider_name, "model": getattr(provider, "model", ""),
    })
    reply = await provider.complete(
        system=prompts.MONITOR_SYSTEM_PROMPT,
        user=prompts.MONITOR_USER_PROMPT.format(**monitor.monitor_context(
            message=state.message, draft=state.draft,
            draft_words=state.draft_words,
            prev_draft_words=state.prev_draft_words,
            history=state.history, notes=state.notes,
            selection=state.selection, previous=state.prev_activity,
        )),
        temperature=0.0,
        max_tokens=400,
    )
    activity, confidence, reason = monitor.parse_llm_decision(reply.text)
    return {
        "decided": activity,
        "confidence": confidence,
        "reason": reason,
        "model": reply.model,
        "provider": reply.provider,
        "prompt_version": prompts.MONITOR_PROMPT_VERSION,
    }


async def activity_monitor(state: TurnState) -> TurnState:
    """Decide which writing activity this turn should be met in.

    Neither the student nor the researcher sets this. An LLM judges it from the
    whole context; the transparent rule in graph/monitor.py is the fallback
    when no LLM is reachable, and is recorded alongside as a baseline either
    way.
    """
    state.visit("activity_monitor")
    rules = monitor.decide(monitor.MonitorInput(
        message_label=state.cognitive,
        intent=state.intent,
        draft_words=state.draft_words,
        prev_draft_words=state.prev_draft_words,
        has_selection=bool(state.selection.strip()),
        previous=state.prev_activity,
    ))
    rules_evidence = rules.as_evidence()

    task = state.monitor_task or asyncio.ensure_future(_monitor_judgement(state))
    state.monitor_task = None
    llm, llm_error = None, ""
    try:
        llm = await task
    except LookupError:
        llm, llm_error = None, ""
    except Exception as exc:
        llm, llm_error = None, str(exc)[:200]
        log.warning("activity_monitor: LLM judgement failed (%s); using rules", exc)

    want = state.fidelity.pop("_monitor_requested", {})
    if llm:
        fidelity.record(state, "monitor", requested_provider=want.get("provider", ""),
                        requested_model=want.get("model", ""),
                        provider=llm["provider"], model=llm["model"])
    elif llm_error:
        fidelity.record(state, "monitor", requested_provider=want.get("provider", ""),
                        requested_model=want.get("model", ""), status="rules", error=llm_error)
    # (No entry when the condition runs the offline scaffold: the rule is then
    # the intended Monitor, not a substitute for one.)

    if llm:
        activity = llm["decided"]
        state.effective_activity = activity
        state.activity_evidence = {
            "method": "llm",
            **llm,
            "previous": state.prev_activity,
            "switched": bool(state.prev_activity) and activity != state.prev_activity,
            "rules": rules_evidence,
            "agrees_with_rules": activity == rules.activity,
        }
        return state

    state.effective_activity = rules.activity
    state.activity_evidence = {
        **rules_evidence,
        "method": "rules",
        "rules": rules_evidence,
        **({"llm_error": llm_error} if llm_error else {}),
    }
    return state


# ---------------------------------------------------------------------------
# Node 2 - Role Arbiter
# ---------------------------------------------------------------------------

def choose_support_move(state: TurnState) -> str:
    """How the role should meet this request. Resolves help-seeking type x
    request form x writing activity into one move (prompts.SUPPORT_MOVES).

    Order matters: a request to write for them is declined whatever else is
    true; a question with one right answer gets that answer (Florence's H6 -
    a spelling question is not a prompt for reflection); an open direction is
    met with options, never a pick (H7); everything else is answered first,
    then reflected on (H5).
    """
    if state.may_produce_prose:
        return "generate"
    if state.intercepted:
        return "decline_and_redirect"
    if state.request_form == "direct":
        return "direct_answer"
    if state.intent == "brainstorm" or state.effective_activity == "planning":
        return "open_options"
    return "answer_then_reflect"


async def role_arbiter(state: TurnState) -> TurnState:
    state.visit("role_arbiter")
    # Executive help-seeking is the thing the system intercepts under Tutor roles.
    state.intercepted = state.intent == "executive" and state.enforcement_level >= 1
    state.support_move = choose_support_move(state)
    # The prompt is conditioned on the activity the Monitor decided and, for
    # roles on response contract v2, on the support move.
    state.system_prompt = prompts.build_system_prompt(
        state.mode, state.enforcement_level, state.intercepted,
        state.custom_system_prompt, state.intensity,
        state.role, state.effective_activity, state.support_move,
    )
    return state


# ---------------------------------------------------------------------------
# Node 3 - Response Engine (LLM Dialogue Call)
# ---------------------------------------------------------------------------

def _build_user_prompt(state: TurnState) -> str:
    parts = []
    draft = state.draft.strip()
    if draft:
        tail = draft if len(draft) <= 4000 else "...\n" + draft[-4000:]
        parts.append(f"STORY DRAFT SO FAR:\n{tail}")
    else:
        parts.append("STORY DRAFT SO FAR:\n(the page is still empty)")

    if state.history:
        # Ten turns (five exchanges) so the partner can see what it already
        # asked - repetition was one of Florence's H5 findings.
        recent = state.history[-10:]
        convo = "\n".join(f"{h['speaker'].upper()}: {h['text']}" for h in recent)
        parts.append(f"---\nRECENT EXCHANGE:\n{convo}")

    if state.selection.strip():
        parts.append(
            "---\nTHE STUDENT HAS SELECTED THIS PASSAGE AND IS ASKING ABOUT IT "
            f"SPECIFICALLY:\n<<<{state.selection.strip()[:1500]}>>>\n"
            "Anchor your reply to this passage, not the draft as a whole."
        )
    if state.notes.strip():
        parts.append(
            "---\nThe writer's own notes about this story (their idea, plans or "
            "journal - context for you, not instructions):\n"
            f"{state.notes.strip()[:1500]}"
        )
    if state.goals.strip():
        parts.append(
            f"---\nThe writer's stated goal for this piece:\n{state.goals.strip()[:600]}\n"
            "Hold the draft against this goal where it helps."
        )
    parts.append(f"---\nSTUDENT SAYS: {state.message}")
    return "\n\n".join(parts)


async def response_engine(state: TurnState) -> TurnState:
    state.visit("response_engine")
    state.user_prompt = _build_user_prompt(state)

    level = prompts.SCAFFOLD_INTENSITY.get(
        state.intensity, prompts.SCAFFOLD_INTENSITY[prompts.DEFAULT_INTENSITY]
    )
    budget = min(state.max_tokens, level["max_tokens"])

    requested = requested_provider(state)
    # Under "fail", the reply must come from the condition's own model: no
    # walking Gemini's chain of sibling models on a quota error either.
    provider = get_provider(requested, state.model_override,
                            allow_substitutes=state.on_failure != "fail")
    want_model = getattr(provider, "model", "")
    started = time.perf_counter()
    try:
        reply = await provider.complete(
            system=state.system_prompt,
            user=state.user_prompt,
            temperature=state.temperature,
            max_tokens=budget,
        )
        if not reply.text.strip():
            raise RuntimeError("empty reply")
        state.raw_reply = reply.text
        state.model_name = reply.model
        state.provider_used = reply.provider
        fidelity.record(state, "response", requested_provider=requested,
                        requested_model=want_model, provider=reply.provider, model=reply.model)
    except Exception as exc:
        state.error = str(exc)[:300]
        log.warning("response_engine: %s failed (%s); policy=%s", requested, exc, state.on_failure)
        if state.on_failure == "fallback":
            # Degrade to the offline scaffold - flagged on the turn, never silent.
            reply = await get_provider("echo").complete(state.system_prompt, state.user_prompt)
            state.raw_reply = reply.text
            state.model_name = reply.model
            state.provider_used = "echo (fallback)"
            state.delivery = "fallback"
            fidelity.record(state, "response", requested_provider=requested,
                            requested_model=want_model, provider="echo", model=reply.model,
                            status="fallback", error=str(exc))
        else:
            # Substitute nothing: every reply on record came from the intended
            # model, and the student is told plainly that this one didn't come.
            state.delivery = "failed"
            state.provider_used = ""
            fidelity.record(state, "response", requested_provider=requested,
                            requested_model=want_model, status="failed", error=str(exc))
    state.latency_ms = int((time.perf_counter() - started) * 1000)
    return state


# Shown to the student when the condition's model could not answer and the
# condition's policy is to fail visibly rather than substitute.
UNAVAILABLE_NOTICE = (
    "Your writing partner couldn't respond just now. Please try again in a moment."
)


# ---------------------------------------------------------------------------
# Node 4 - Prompt Template Formatter
# ---------------------------------------------------------------------------

def _split_probes(blob: str, limit: int = 3) -> list[str]:
    raw = re.split(r"\s*\|\s*|\n\s*[-*•]\s*", blob)
    out = []
    for p in raw:
        p = p.strip().strip('"').lstrip("0123456789.) ").strip()
        if 3 < len(p) <= 120:
            out.append(p)
    return out[:limit]


def _contract(state: TurnState) -> str:
    """The role's response contract. A Ghost always uses the control prompt's
    RESPONSE/PROBES envelope, whatever its role record says."""
    if state.may_produce_prose or not state.role:
        return prompts.RESPONSE_CONTRACT_V1
    return state.role.get("response_contract") or prompts.RESPONSE_CONTRACT_V1


async def response_formatter(state: TurnState) -> TurnState:
    state.visit("response_formatter")
    if state.delivery == "failed":
        state.response_text = UNAVAILABLE_NOTICE
        return state

    text = state.raw_reply.strip()

    if _contract(state) == prompts.RESPONSE_CONTRACT_V2:
        # v2 asks for the answer only. Models keep v1 habits now and then:
        # drop a stray label and any trailing list of follow-up questions.
        text = re.sub(r"(?is)\s*PROBES:.*$", "", text)
        text = re.sub(r"(?i)^\s*RESPONSE:\s*", "", text)
        # The chat shows plain text, so markdown emphasis would appear as
        # literal asterisks ("**accommodate**").
        text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
        text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
        state.response_text = re.sub(r"\s*\n\s*", " ", text).strip()
        state.probes = []
        return state

    limit = prompts.SCAFFOLD_INTENSITY.get(
        state.intensity, prompts.SCAFFOLD_INTENSITY[prompts.DEFAULT_INTENSITY]
    )["probe_count"]

    m_resp = re.search(r"RESPONSE:[ \t]*\n?(.*?)(?=\s*PROBES:|\Z)", text, re.S | re.I)
    m_probe = re.search(r"PROBES:\s*(.*)", text, re.S | re.I)

    if m_resp and m_resp.group(1).strip():
        state.response_text = m_resp.group(1).strip()
    elif m_resp:
        # "RESPONSE:" was present but empty. Everything before PROBES is still
        # the reply; falling through to the salvage path recovers it.
        state.response_text = re.sub(r"(?i)RESPONSE:\s*", "", text.split("PROBES:")[0]).strip()
    else:
        # Model ignored the envelope. Salvage: treat trailing questions as probes.
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        qs = [ln for ln in lines if ln.endswith("?")]
        state.response_text = " ".join(ln for ln in lines if ln not in qs).strip() or text
        state.probes = _split_probes(" | ".join(qs[-3:]), limit)

    if m_probe:
        state.probes = _split_probes(m_probe.group(1), limit)

    state.response_text = re.sub(r"(?is)\s*PROBES:.*$", "", state.response_text)
    state.response_text = re.sub(r"(?i)^\s*RESPONSE:\s*", "", state.response_text)
    state.response_text = re.sub(r"\s*\n\s*", " ", state.response_text).strip()

    # Smaller models often ignore the PROBES envelope but still ask good
    # questions inline. Record those as probes - but leave them in the reply:
    # the student view no longer shows probes, so moving a question out of the
    # reply hid it from the student entirely (iteration-4 review).
    if not state.probes:
        inline = re.findall(r"([^.!?]*\?)", state.response_text)
        harvested = [q.strip() for q in inline if 12 < len(q.strip()) <= 120]
        if harvested:
            state.probes = harvested[:limit]
            state.enforcement.append("harvested_inline_probes")

    return state


# ---------------------------------------------------------------------------
# Agency Enforcer - HLD 6.1 Module 2(iii)
# ---------------------------------------------------------------------------

# Words that are capitalised for reasons other than being a name.
_STOPCAPS = {
    "the", "a", "an", "i", "it", "he", "she", "they", "we", "you", "this",
    "that", "what", "where", "when", "why", "how", "if", "but", "and", "so",
    "her", "his", "their", "there", "then", "captain", "doctor", "mr", "mrs",
}


def _draft_names(draft: str) -> set[str]:
    """Proper nouns the student invented - character and place names.

    Only words capitalised mid-sentence: a sentence-initial "Nobody" or
    "Everyone" is not a name (it made the enforcer read "'Nobody argued'
    feels abrupt" as narration about a character called Nobody).
    """
    text = draft.strip()
    names = set()
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\b", text):
        before = text[:m.start()].rstrip()
        at_start = not before or (before[-1] in ".!?" and not _TITLE_END.search(before))
        if not at_start and m.group(1).lower() not in _STOPCAPS:
            names.add(m.group(1).lower())
    return names


# "Ms." / "Dr." end in a full stop but don't end a sentence: "Ms. Okafor" is a name.
_TITLE_END = re.compile(r"\b(?:Ms|Mr|Mrs|Dr|St|Prof)\.$")


# Past-tense narration: a run of -ed/irregular verbs.
_PAST_VERBS = re.compile(
    r"\b(\w+ed|was|were|had|looked|felt|saw|knew|said|stood|moved|turned|"
    r"lingered|reached|watched|whispered|walked|ran|began|found|took|came|went|"
    r"sat|held|left|thought|told|made|kept|stared|paused|hung|fell|rose|grew|lay|"
    r"drew|wrote|spoke|broke|shook|struck|swept|slept|wept|crept|knelt|bent|sank|"
    r"rang|sang|swung|stuck|caught|brought|bought|fought|sought|taught|meant|"
    r"heard|led|met|read|sent|spent|stole|chose|froze|woke|wore|tore|bore|gave|"
    r"got|let|put|set|shut|cut|hit|became|seemed|remained)\b", re.I
)
# Talk *about* a story names its parts or its writer; the story itself rarely
# does. A sentence with one of these is analysis, not narration.
_ANALYTIC = re.compile(
    r"\b(you|your|yours|you're|yourself|draft|story|stories|reader|readers|scene|"
    r"scenes|paragraph|line|lines|sentence|sentences|chapter|character|characters|"
    r"narrative|plot|ending|opening|passage|wording|phrase|phrasing|tone|pacing|"
    r"beat|arc|protagonist|narrator|point of view)\b", re.I
)
_THIRD_PERSON = re.compile(r"\b(he|she|they|him|her|his|hers|them|their)\b", re.I)
_SECOND_PERSON = re.compile(r"\b(you|your|you're|yours|yourself)\b", re.I)
# Sentence boundaries - but not after a title ("Ms. Okafor"), which split a
# name in half and left "...spoke volumes. Ms." on screen in testing.
# A closing quote after the full stop still ends the sentence ('...announced." What').
_SENTENCES = re.compile(
    r"(?<!\bMs\.)(?<!\bMr\.)(?<!\bDr\.)(?<!\bSt\.)(?<!\bMrs\.)(?<=[.!?])\s+"
    r"|(?<=[.!?][\"”’'])\s+"
)


def _statements(text: str) -> str:
    """The text without its questions. A question does not make prose around
    it any less pasteable - the old check skipped any reply containing one '?'
    (iteration-4 review, hole 1)."""
    return " ".join(s for s in _SENTENCES.split(text) if not s.rstrip().endswith("?"))


def _looks_like_narrative(text: str, draft: str) -> bool:
    """Would this paste into the story and read as the student's own prose?

    Small models are the reason this exists. They comply with "do not write the
    story" in the abstract and then quietly continue the scene anyway, which no
    keyword filter catches. Signals, on the reply's statements (its questions
    set aside):
      - past-tense narration (density of narrative verbs);
      - about the story's people: the draft's own character names, or - when
        the draft has no names yet - third-person pronouns (hole 2);
      - not addressed to the writer: talk *about* a story says "you/your";
        story prose almost never does.
    """
    body = _statements(text)
    words = body.split()
    if len(words) < 8:
        return False
    tokens = {t.lower() for t in re.findall(r"[A-Za-z]+", body)}
    names = _draft_names(draft)
    # Match possessives too - "Sarah's gaze" names the cast just as "Sarah" does.
    about_people = bool(names & tokens) or (
        len(_THIRD_PERSON.findall(body)) / len(words) >= 0.05
    )
    past_density = len(_PAST_VERBS.findall(body)) / len(words)
    addressed = len(_SECOND_PERSON.findall(body)) / len(words)
    return about_people and past_density >= 0.06 and addressed < 0.03


# A quoted word or phrase. Single quotes count only when they open after a
# space, so possessives ("Okafor's ... students'") never pair up as a quote.
_QUOTING = re.compile(r'["“][^"”]{1,80}["”]|(?:^|\s)[\'‘][^\'’]{1,60}[\'’](?=[\s.,;:!?]|$)')


# Marks of advice or commentary rather than narration. Story prose in the past
# tense has none of them; a tutor's sentence nearly always has one.
_MODAL = re.compile(r"\b(could|might|should|would|can|may|must|will|shall|need to|want to)\b", re.I)
_PRESENT = re.compile(
    r"\b(is|are|am|isn't|aren't|means|refers|feels|seems|looks|sounds|reads|works|"
    r"has|have|does|do|doesn't|don't|gives|makes|shows|creates|leaves|lands|matters|"
    r"depends|suggests|stays|keeps|holds|sets)\b", re.I)
_ADVICE_START = re.compile(
    r"^\W*(?:(?:first|second|third|fourth|next|then|finally|also|or|alternatively|lastly)\W+)?"
    r"(consider|try|compare|think|ask|look|notice|focus|imagine|explore|decide|follow|show|"
    r"center|centre|stay|step|jump|open|end|frame|structure|alternate|use|"
    r"add|cut|read|write|describe|keep|start|begin|let|maybe|perhaps|instead|if|when|"
    r"one|another|here|there's|there are|sure|yes|no)\b", re.I)
# Present tense after a third-person subject ("she secretly designs", "someone
# who comes to her"): describing a possible direction, not narrating one.
_PRESENT_3RD = re.compile(
    r"\b(?:she|he|it|who|someone|everyone|nobody|everybody)\s+(?:\w+ly\s+)?"
    r"(?!was\b|has\b|is\b|always\b|never\b)[a-z]+[^s\W]s\b", re.I)
# "-ed" words that are almost always adjectives or set phrases, not narration.
_NOT_PAST = {"used", "based", "called", "related", "interested", "supposed", "detailed",
             "advanced", "limited", "focused", "concerned", "complicated", "unexpected"}


def _past_verbs(sentence: str) -> list[str]:
    return [v for v in _PAST_VERBS.findall(sentence) if v.lower() not in _NOT_PAST]


def _narrative_sentence(sentence: str, draft_tokens: set[str], cast: frozenset = frozenset()) -> bool:
    """One sentence of story prose: past-tense narration with none of the
    marks of advice or commentary, and not a retelling of the student's text.

    A density threshold missed single-sentence narration ("The essays flowed
    onto the floor, each page a testament...": one verb in thirteen words) and
    cut real help ("Consider expanding how the silence unfolded").
    """
    words = sentence.split()
    if len(words) < 4 or sentence.rstrip().endswith("?") or _SECOND_PERSON.search(sentence):
        return False
    # A sentence whose subject is one of the story's people is narration
    # whatever nouns it uses ("Ms. Okafor focused on one, a narrative penned
    # by..."); otherwise words like "scene" or "reader" mark commentary.
    lead = [t.lower() for t in re.findall(r"[A-Za-z]+", sentence)[:3]]
    about_cast = bool(lead) and (lead[0] in {"he", "she", "they"} or bool(set(lead) & cast))
    if not about_cast and _ANALYTIC.search(sentence):
        return False
    if _QUOTING.search(sentence):
        return False  # quoting words to talk about them ("'Who' is correct in ...")
    if (_MODAL.search(sentence) or _PRESENT.search(sentence) or _ADVICE_START.search(sentence)
            or _PRESENT_3RD.search(sentence)):
        return False
    if not _past_verbs(sentence):
        return False
    content = [t for t in re.findall(r"[a-z']+", sentence.lower()) if len(t) >= 4]
    if content and sum(t in draft_tokens for t in content) / len(content) >= 0.6:
        return False  # retelling their own text back to them
    return True


def _strip_narrative_sentences(text: str, theirs: str) -> tuple[str, int]:
    """Remove sentences that continue the story; keep the help around them.

    Replacing the whole reply when one sentence narrated threw away the
    genuine question that often followed it; letting it through (one '?'
    anywhere used to be enough) put story prose in front of the student.
    """
    draft_tokens = set(re.findall(r"[a-z']+", theirs.lower()))
    cast = frozenset(_draft_names(theirs))
    sentences = _SENTENCES.split(text.strip())
    kept = [x for x in sentences if not _narrative_sentence(x, draft_tokens, cast)]
    return " ".join(kept), len(sentences) - len(kept)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text.lower())).strip()


_DIALOGUE_RE = re.compile(r'["“][^"”]{25,}["”]\s*,?\s*(?:he|she|they|\w+)\s+(?:said|asked|replied|whispered|shouted)', re.I)
# Quoted spans, paired left to right. Matching "a long run between two quote
# marks" instead paired the closing quote of one word with the opening quote
# of the next - 'It is "whom." If you would use "him"' lost everything between
# them (caught by the evaluation suite on its first run).
_QUOTED_RE = re.compile(r'"([^"]*)"|“([^”]*)”')
_LEAD_IN_RE = re.compile(r"(?:for example|here'?s (?:an? )?(?:example|version|how)|something like|you could write|try this|like this:)\s*:?\s*", re.I)
_QUOTE_START = re.compile(r'^\s*["“‘\']')


def _strip_demonstrations(text: str, draft: str) -> tuple[str, bool]:
    """Cut a lead-in only when what follows it is story text.

    The old rule cut everything after "try this" or "for example", so
    "Try this: read it aloud and mark where you stumble" lost the actual help
    (hole 3). Now the cut happens only if the text after the lead-in opens with
    a quotation or reads as narrative.
    """
    m = _LEAD_IN_RE.search(text)
    if not m:
        return text, False
    after = text[m.end():]
    first = _SENTENCES.split(after.strip(), maxsplit=1)[0] if after.strip() else ""
    if _QUOTE_START.match(after) or (first and _looks_like_narrative(first, draft)):
        return text[:m.start()].rstrip(" ,;:-"), True
    return text, False


def _strip_quoted_prose(text: str, draft: str) -> tuple[str, bool]:
    """Remove sentences that hand the student wording in quotation marks.

    The whole sentence goes, not just the quote: cutting the quote alone left
    "Try starting with instead of ..." in testing. Quoting the student's *own*
    words back to them is fine - that is pointing at their text - so a quote
    found in what they wrote (the draft, their message, the selected passage)
    is kept.
    """
    draft_n = _norm(draft)

    def offending(sentence: str) -> bool:
        for m in _QUOTED_RE.finditer(sentence):
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            if len(inner.split()) >= 5 and _norm(inner) not in draft_n:
                return True
        return False

    sentences = _SENTENCES.split(text.strip())
    kept = [x for x in sentences if not offending(x)]
    return " ".join(kept), len(kept) != len(sentences)


async def agency_enforcer(state: TurnState) -> TurnState:
    state.visit("agency_enforcer")
    if state.delivery == "failed":
        # Nothing was generated, so there is nothing to check.
        state.enforcement.append("no_reply_provider_failed")
        return state
    text = state.response_text

    # The enforcer always runs and always records that it ran. What it *does*
    # depends on the role's contract rather than an absolute rule.
    #
    # A Ghost (archetype=ghost, may_produce_prose=True, enforcement_level=0) is
    # meant to write prose, so there is nothing to strip - but the turn is still
    # logged as having passed through here, which is the control-arm telemetry
    # the old strictness==0 early-return silently dropped.
    if state.may_produce_prose:
        state.enforcement.append("prose_permitted_by_role")
        if not text.strip():
            state.enforcement.append("substituted_empty_response")
            state.response_text = (
                "That came back empty. Try asking again, or rephrase what you "
                "are stuck on."
            )
        else:
            state.response_text = text.strip()
        return state

    # From here down the role forbids prose.
    if not text.strip():
        state.enforcement.append("substituted_empty_response")
        state.response_text = (
            "That came back empty. Try asking again, or rephrase what you "
            "are stuck on."
        )
        return state

    if _DIALOGUE_RE.search(text):
        state.enforcement.append("stripped_dialogue")
        text = _DIALOGUE_RE.sub("", text)

    text, cut = _strip_demonstrations(text, state.draft)
    if cut:
        state.enforcement.append("stripped_demonstration")

    if state.enforcement_level >= 2:
        theirs = "\n".join((state.draft, state.message, state.selection))
        text, quoted = _strip_quoted_prose(text, theirs)
        if quoted:
            state.enforcement.append("stripped_quoted_prose")

    if (cut or "stripped_quoted_prose" in state.enforcement) and (
        len(text.split()) < 6 or text.rstrip().endswith(":")
    ):
        # Stripping the suggested wording left only its lead-in ("How about:").
        state.enforcement.append("replaced_stub")
        text = ("That wording should come from you. What does this line need to do "
                "for the reader at this point in the story?")

    # The decisive check: narrative continuation of the student's story.
    # Sentence by sentence first; the whole reply only goes if what's left is
    # not worth showing, or still reads as narrative.
    if state.enforcement_level >= 1:
        kept, removed = _strip_narrative_sentences(
            text, "\n".join((state.draft, state.message, state.selection)))
        if removed:
            state.enforcement.append("stripped_narrative_sentences")
            text = kept
        # Backstop for a longer block the sentence test let through (e.g. story
        # prose that happens to use the word "line" in every sentence).
        long_block = len(_statements(text).split()) >= 25 and _looks_like_narrative(text, state.draft)
        if (removed and len(text.split()) < 6) or long_block:
            state.enforcement.append("blocked_narrative_continuation")
            text = (
                "I started writing the scene there, which is not mine to write. "
                "Let's find the way in instead."
            )

    # A long run of statements is a prose block, question or no question.
    if state.enforcement_level >= 2:
        cap = 160 if state.intensity == "deep" else 110
        if len(_statements(text).split()) > cap:
            state.enforcement.append("truncated_prose_block")
            sentences = _SENTENCES.split(text)
            questions = [x for x in sentences if x.rstrip().endswith("?")]
            kept = [x for x in sentences if not x.rstrip().endswith("?")][:2]
            text = " ".join(kept + questions[-1:])

    text = text.strip()
    if not text:
        state.enforcement.append("substituted_empty_response")
        text = "Let's stay with your draft for a moment rather than adding to it."

    state.response_text = text

    if _contract(state) == prompts.RESPONSE_CONTRACT_V2:
        # v2 produces no probes, and the student view shows none.
        return state

    # A chip that repeats a sentence already in the reply is pure noise,
    # whichever path produced it.
    if state.probes and state.response_text:
        deduped = [p for p in state.probes if p not in state.response_text]
        if deduped != state.probes and deduped:
            state.probes = deduped

    if not state.probes:
        state.enforcement.append("synthesised_probes")
        fallback = [
            "What does your character want right now?",
            "What would make this harder?",
            "Which sentence are you least sure about?",
        ]
        limit = prompts.SCAFFOLD_INTENSITY.get(
            state.intensity, prompts.SCAFFOLD_INTENSITY[prompts.DEFAULT_INTENSITY]
        )["probe_count"]
        state.probes = fallback[:limit]
    return state
