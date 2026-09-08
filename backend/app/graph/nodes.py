"""The five graph nodes.

Maps directly onto HLD 7.1 and 6.1 Module 2:

  intent_classifier   -> Node 1: Intent & Help-Seeking Classifier
  role_arbiter        -> Node 2: Role Arbiter (resolves role × activity × intent)
  response_engine     -> Node 3: Response Engine (LLM dialogue call)
  response_formatter  -> Node 4: Prompt Template Formatter
  agency_enforcer     -> Module 2(iii): Agency Enforcer

Written as explicit functions rather than a LangGraph build so the path each
turn takes can be recorded and surfaced in the interface.
"""
import logging
import re
import time

from .. import prompts
from ..providers import get_provider
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

_VALID = {"executive", "instrumental", "brainstorm", "reflection"}
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

    if _EXEC_RE.search(state.message) and not _INSTRUMENTAL_VETO.search(state.message):
        state.intent = "executive"

    from ..config import settings
    # Classify on the light model when we are on Gemini; other providers
    # classify on whatever they are already running.
    classifier_model = (
        settings.gemini_classifier_model
        if (state.provider_name or settings.effective_provider) == "gemini"
        else state.model_override
    )
    provider = get_provider(state.provider_name, classifier_model)
    try:
        reply = await provider.complete(
            system="You are a precise classifier. Reply with exactly two words.",
            user=prompts.CLASSIFIER_PROMPT.format(message=state.message),
            temperature=0.0,
            max_tokens=12,
        )
        words = [w.strip(".,:;\"'") for w in reply.text.strip().lower().split()]
        if not state.intent:
            state.intent = next((w for w in words if w in _VALID), "instrumental")
        state.cognitive = next((w for w in words if w in _VALID_COGNITIVE), "")
    except Exception as exc:
        log.warning("intent_classifier failed (%s); assuming instrumental", exc)
        # Never let classification failure break the turn - default to the
        # pedagogically safe assumption.
        if not state.intent:
            state.intent = "instrumental"

    if not state.cognitive:
        state.cognitive = _cognitive_fallback(state.message)
    return state


def _cognitive_fallback(message: str) -> str:
    for label, pattern in _COGNITIVE_HINTS:
        if re.search(pattern, message, re.I):
            return label
    # Nothing matched: "other", not "planning". A wrong default here quietly
    # skews the headline distribution (defect D3).
    return "other"


# ---------------------------------------------------------------------------
# Node 2 - Role Arbiter
# ---------------------------------------------------------------------------

async def role_arbiter(state: TurnState) -> TurnState:
    state.visit("role_arbiter")
    # Executive help-seeking is the thing the system intercepts under Tutor roles.
    state.intercepted = state.intent == "executive" and state.enforcement_level >= 1
    # Phase 2: the prompt is conditioned on the writing activity. The writer's
    # own declaration (Flower & Hayes' Monitor) wins; the classifier's guess is
    # the fallback when they have not declared one.
    state.effective_activity = state.declared_activity or state.cognitive
    state.system_prompt = prompts.build_system_prompt(
        state.mode, state.enforcement_level, state.intercepted,
        state.custom_system_prompt, state.intensity,
        state.role, state.effective_activity,
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
        recent = state.history[-6:]
        convo = "\n".join(f"{h['speaker'].upper()}: {h['text']}" for h in recent)
        parts.append(f"---\nRECENT EXCHANGE:\n{convo}")

    if state.selection.strip():
        parts.append(
            "---\nTHE STUDENT HAS SELECTED THIS PASSAGE AND IS ASKING ABOUT IT "
            f"SPECIFICALLY:\n<<<{state.selection.strip()[:1500]}>>>\n"
            "Anchor your reply to this passage, not the draft as a whole."
        )
    if state.declared_activity:
        parts.append(
            f"---\nThe writer says they are currently {state.declared_activity}. "
            "Meet them in that activity."
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

    provider = get_provider(state.provider_name, state.model_override)
    started = time.perf_counter()
    try:
        reply = await provider.complete(
            system=state.system_prompt,
            user=state.user_prompt,
            temperature=state.temperature,
            max_tokens=budget,
        )
        state.raw_reply = reply.text
        state.model_name = reply.model
        state.provider_used = reply.provider
    except Exception as exc:
        state.error = str(exc)
        # Degrading silently would hide real outages behind plausible output,
        # so the reason is always logged even though the student never sees it.
        log.warning("response_engine: %s failed (%s); falling back to offline scaffold",
                    state.provider_name or "default", exc)
        # Graceful degradation: fall back to the offline scaffold rather than
        # showing the student an error where a question should be.
        fallback = get_provider("echo")
        reply = await fallback.complete(state.system_prompt, state.user_prompt)
        state.raw_reply = reply.text
        state.model_name = reply.model
        state.provider_used = "echo (fallback)"
    state.latency_ms = int((time.perf_counter() - started) * 1000)
    return state


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


async def response_formatter(state: TurnState) -> TurnState:
    state.visit("response_formatter")
    text = state.raw_reply.strip()
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
    # questions inline. Harvest those before resorting to generic fallbacks -
    # a draft-specific question beats a canned one every time.
    if not state.probes:
        inline = re.findall(r"([^.!?]*\?)", state.response_text)
        harvested = [q.strip() for q in inline if 12 < len(q.strip()) <= 120]
        if harvested:
            # Keep the reply from repeating verbatim what the chip already says.
            if state.response_text.endswith(harvested[-1]):
                trimmed = state.response_text[: -len(harvested[-1])].strip(" ,;-")
                if len(trimmed.split()) >= 5:
                    state.response_text = trimmed
                else:
                    # The question *is* the whole reply; showing it twice is noise.
                    harvested = harvested[:-1] if len(harvested) > 1 else []
            if harvested:
                state.probes = harvested[:limit]
                state.enforcement.append("harvested_inline_probes")

    return state


# ---------------------------------------------------------------------------
# Agency Enforcer - HLD 6.1 Module 2(iii)
# ---------------------------------------------------------------------------

# Prose the student could paste straight into the story. Two signals: a long
# run of declarative sentences, or quoted dialogue.
# Words that are capitalised for reasons other than being a name.
_STOPCAPS = {
    "the", "a", "an", "i", "it", "he", "she", "they", "we", "you", "this",
    "that", "what", "where", "when", "why", "how", "if", "but", "and", "so",
    "her", "his", "their", "there", "then", "captain", "doctor", "mr", "mrs",
}


def _draft_names(draft: str) -> set[str]:
    """Proper nouns the student invented - character and place names."""
    caps = re.findall(r"\b([A-Z][a-z]{2,})\b", draft)
    return {c.lower() for c in caps if c.lower() not in _STOPCAPS}


# Past-tense narration: a run of -ed/irregular verbs with no question in sight.
_PAST_VERBS = re.compile(
    r"\b(\w+ed|was|were|had|looked|felt|saw|knew|said|stood|moved|turned|"
    r"lingered|reached|watched|whispered|walked|ran|began|found)\b", re.I
)


def _looks_like_narrative(text: str, draft: str) -> bool:
    """Would this paste into the story and read as the student's own prose?

    Small models are the reason this exists. They comply with "do not write the
    story" in the abstract and then quietly continue the scene anyway, which no
    keyword filter catches. Two signals together are decisive: the reply asks
    nothing, and it is narrating using the student's own character names.
    """
    if "?" in text:
        return False
    words = text.split()
    if len(words) < 6:
        return False
    names = _draft_names(draft)
    # Match possessives too - "Sarah's gaze" names the cast just as "Sarah" does.
    tokens = {t.lower() for t in re.findall(r"[A-Za-z]+", text)}
    mentions_cast = bool(names & tokens)
    past_density = len(_PAST_VERBS.findall(text)) / max(len(words), 1)
    return mentions_cast and past_density >= 0.06


_DIALOGUE_RE = re.compile(r'["“][^"”]{25,}["”]\s*,?\s*(?:he|she|they|\w+)\s+(?:said|asked|replied|whispered|shouted)', re.I)
_LEAD_IN_RE = re.compile(r"(?:for example|here'?s (?:an? )?(?:example|version|how)|something like|you could write|try this|like this:)\s*:?\s*", re.I)


async def agency_enforcer(state: TurnState) -> TurnState:
    state.visit("agency_enforcer")
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

    # From here down the role forbids prose. This is byte-for-byte the pre-role
    # strictness>=1 path, with enforcement_level standing in for strictness.
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

    if _LEAD_IN_RE.search(text):
        state.enforcement.append("stripped_demonstration")
        text = _LEAD_IN_RE.split(text)[0]

    # The decisive check: narrative continuation using the student's own cast.
    # Enforced at enforcement_level >= 1 for tutor/partner roles; Ghost is exempt
    # because producing prose is its declared behaviour.
    if state.enforcement_level >= 1 and _looks_like_narrative(text, state.draft):
        state.enforcement.append("blocked_narrative_continuation")
        text = (
            "I started writing the scene there, which is not mine to write. "
            "Let's find the way in instead."
        )

    # A long block with no question mark is prose, not scaffolding.
    # Enforced at enforcement_level >= 2.
    if state.enforcement_level >= 2 and len(text.split()) > 110 and "?" not in text:
        state.enforcement.append("truncated_prose_block")
        sentences = re.split(r"(?<=[.!?])\s+", text)
        text = " ".join(sentences[:2])

    text = text.strip()
    if not text:
        state.enforcement.append("substituted_empty_response")
        text = "Let's stay with your draft for a moment rather than adding to it."

    state.response_text = text

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
