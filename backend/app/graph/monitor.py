"""The Monitor - decides which writing activity the Tutor should meet.

Flower & Hayes (1981) name four components of the writing process: Planning,
Translating, Reviewing, and the Monitor - "a writing strategist which
determines when the writer moves from one process to another." Iteration 2
externalised the Monitor as a student-facing toggle. Iteration 3 takes it away
from the student (and from the researcher): the system decides, every turn.

Two ways of deciding, both recorded on every turn:

  LLM (primary)  - an LLM reads the whole situation - the message, the draft
                   and how it changed, the recent exchange, the writer's notes,
                   the selected passage, the previous decision - and judges the
                   process, with a confidence and a one-line reason. See
                   prompts.MONITOR_SYSTEM_PROMPT. Context matters: "thanks", or
                   "write this for me", only mean something against what the
                   writer has been doing.

  Rules (fallback + baseline) - the transparent weighted-evidence rule below.
                   It decides only when no LLM is reachable (offline scaffold,
                   exhausted quota, unparseable reply), so the demo never
                   breaks; but it is computed on every turn and stored beside
                   the LLM's call, so a researcher can measure how often the
                   LLM departs from what surface signals alone would say.

Rule constraints, each from the literature:

  * Any activity can follow any other. F&H: "people do not march through these
    processes in a simple 1, 2, 3 order"; processes embed and recurse. So there
    is no transition table and no ordering - only a small inertia bonus for
    staying put.
  * The writer's instruction is the primary evidence. Chakrabarty et al.
    (C&C '24) label writing activity from the instruction itself, so the
    classifier's label carries the largest weight.
  * The text produced so far is part of F&H's task environment: an almost-empty
    page leans Planning; a draft that grew since the last ask leans
    Translating; a draft that shrank (revision deletes) leans Reviewing.
  * Asking about a selected passage is working on existing text (C&C '24 §3.2)
    - Reviewing or Translating, not Planning.
  * Brainstorming is F&H's "generating" sub-process of Planning.
  * An aside ("thanks", "ok") carries no evidence, so inertia holds.

If the rule's weights change, bump MONITOR_VERSION; if the LLM prompt changes,
bump prompts.MONITOR_PROMPT_VERSION. Every decision records both, so turns stay
traceable to what decided them (the append-only reasoning of plan defect D1).

Activity labels use the stored spelling: planning | translation | reviewing.
"""
import json
import re
from dataclasses import dataclass, field

MONITOR_VERSION = "monitor-v1"

ACTIVITIES = ("planning", "translation", "reviewing")

# Evidence weights. The message label outweighs any two contextual signals
# combined, so a clear instruction always wins; context decides the unclear ones.
W_MESSAGE = 3.0
W_BRAINSTORM = 0.75
W_SPARSE_DRAFT = 1.5
W_DRAFT_GREW = 1.0
W_DRAFT_SHRANK = 1.0
W_SELECTION_REVIEW = 1.0
W_SELECTION_TRANSLATE = 0.5
W_INERTIA = 0.75

SPARSE_DRAFT_WORDS = 30   # below this, the piece is still mostly an idea
GREW_WORDS = 25           # net words added since the last ask
SHRANK_WORDS = 5          # net words removed since the last ask


@dataclass
class MonitorInput:
    message_label: str = ""       # classifier's cognitive label for this message
    intent: str = ""              # Helsinki help-seeking label
    draft_words: int = 0
    prev_draft_words: int | None = None   # None = first turn in this story
    has_selection: bool = False
    previous: str = ""            # the Monitor's decision on the previous turn


@dataclass
class MonitorDecision:
    activity: str                 # planning | translation | reviewing | "" (no evidence)
    scores: dict[str, float]
    signals: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    previous: str = ""
    switched: bool = False

    def as_evidence(self) -> dict:
        return {
            "version": MONITOR_VERSION,
            "decided": self.activity,
            "scores": self.scores,
            "signals": self.signals,
            "confidence": self.confidence,
            "previous": self.previous,
            "switched": self.switched,
        }


def decide(inp: MonitorInput) -> MonitorDecision:
    scores = {a: 0.0 for a in ACTIVITIES}
    signals: list[dict] = []

    def add(signal: str, activity: str, weight: float, detail: str = "") -> None:
        scores[activity] += weight
        signals.append({"signal": signal, "activity": activity,
                        "weight": weight, "detail": detail})

    if inp.message_label in ACTIVITIES:
        add("message", inp.message_label, W_MESSAGE, "classifier label")

    if inp.intent == "brainstorm":
        add("brainstorm_intent", "planning", W_BRAINSTORM, "widening options = generating")

    if inp.draft_words < SPARSE_DRAFT_WORDS:
        add("sparse_draft", "planning", W_SPARSE_DRAFT, f"{inp.draft_words} words on the page")

    if inp.prev_draft_words is not None:
        delta = inp.draft_words - inp.prev_draft_words
        if delta >= GREW_WORDS:
            add("draft_grew", "translation", W_DRAFT_GREW, f"+{delta} words since last ask")
        elif delta <= -SHRANK_WORDS:
            add("draft_shrank", "reviewing", W_DRAFT_SHRANK, f"{delta} words since last ask")

    if inp.has_selection:
        add("selection", "reviewing", W_SELECTION_REVIEW, "asking about existing text")
        add("selection", "translation", W_SELECTION_TRANSLATE, "asking about existing text")

    if inp.previous in ACTIVITIES:
        add("inertia", inp.previous, W_INERTIA, "previous turn's activity")

    top = max(scores.values())
    if top <= 0:
        # Nothing observable points anywhere. Say so rather than guess: an empty
        # decision means the Tutor answers from its base prompt alone.
        return MonitorDecision(activity="", scores=scores, signals=signals,
                               previous=inp.previous, switched=False)

    leaders = [a for a in ACTIVITIES if scores[a] == top]
    # Ties: stay where we were, else follow the message, else take the first.
    if inp.previous in leaders:
        activity = inp.previous
    elif inp.message_label in leaders:
        activity = inp.message_label
    else:
        activity = leaders[0]

    ordered = sorted(scores.values(), reverse=True)
    total = sum(scores.values())
    confidence = round((ordered[0] - ordered[1]) / total, 3) if total else 0.0

    return MonitorDecision(
        activity=activity,
        scores={a: round(s, 3) for a, s in scores.items()},
        signals=signals,
        confidence=confidence,
        previous=inp.previous,
        switched=bool(inp.previous) and activity != inp.previous,
    )


# --------------------------------------------------------------------------
# LLM judgement
# --------------------------------------------------------------------------

# The LLM is asked for the client's spelling ("translating"); storage uses the
# classifier's ("translation"). Accept either, plus capitalised variants.
_LLM_LABELS = {
    "planning": "planning", "plan": "planning",
    "translating": "translation", "translation": "translation",
    "reviewing": "reviewing", "review": "reviewing", "revising": "reviewing",
}


def monitor_context(
    message: str,
    draft: str,
    draft_words: int,
    prev_draft_words: int | None,
    history: list[dict],
    notes: str,
    selection: str,
    previous: str,
) -> dict:
    """The fields MONITOR_USER_PROMPT is formatted with."""
    if prev_draft_words is None:
        change = "first question in this story"
    else:
        delta = draft_words - prev_draft_words
        change = (f"+{delta} words since the last question" if delta > 0
                  else f"{delta} words since the last question" if delta < 0
                  else "unchanged since the last question")
    text = draft.strip()
    if len(text) > 3000:
        text = "..." + text[-3000:]
    recent = "\n".join(
        f"{h['speaker'].upper()}: {h['text'][:400]}" for h in history[-6:]
    )
    prev_label = {"translation": "translating"}.get(previous, previous)
    return {
        "notes": notes.strip()[:1200] or "(none)",
        "draft": text or "(empty)",
        "draft_words": draft_words,
        "draft_change": change,
        "history": recent or "(no exchange yet)",
        "previous": prev_label or "(none - this is the first judgement)",
        "selection": selection.strip()[:800] or "(none)",
        "message": message.strip(),
    }


def parse_llm_decision(text: str) -> tuple[str, float, str]:
    """(activity, confidence, reason) from the LLM's reply. Raises ValueError.

    Tolerates code fences and chatter around the object; small local models
    rarely return clean JSON.
    """
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON object in monitor reply: {text[:120]!r}")
    data = json.loads(m.group(0))
    label = _LLM_LABELS.get(str(data.get("activity", "")).strip().lower())
    if not label:
        raise ValueError(f"unrecognised activity: {data.get('activity')!r}")
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(data.get("reason", "")).strip()[:300]
    return label, round(confidence, 3), reason
