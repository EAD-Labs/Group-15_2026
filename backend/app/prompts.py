"""The pedagogical core.

Everything here encodes the Helsinki help-seeking distinction that HLD 6.1
Module 2 and constraint 12.2.1 are built around:

  instrumental help-seeking - the learner asks for something that helps them
      do the work themselves (a hint, a question, a perspective, a critique).
      SUPPORT THIS.

  executive help-seeking - the learner asks the system to do the work for them
      ("write the next paragraph", "finish this scene"). This offloads the
      cognitive effort that the learning depends on. INTERCEPT THIS.

The Socratic engine's one inviolable rule: it never returns narrative prose
that could be pasted into the story. It returns questions and angles.
"""

MODES = {
    "learning_scenario": {
        "label": "Learning Scenario",
        "blurb": "A realistic teaching situation used to explore pedagogy.",
        "lens": "pedagogical realism, learner motivation, and what the scenario teaches",
    },
    "educational_narrative": {
        "label": "Educational Narrative",
        "blurb": "A story that carries a concept or lesson inside it.",
        "lens": "narrative craft in service of a concept, and whether the idea lands",
    },
    "design_fiction": {
        "label": "Design Fiction",
        "blurb": "A speculative near-future story that interrogates a technology.",
        "lens": "speculative plausibility, second-order consequences, and critique",
    },
}

# --------------------------------------------------------------------------
# Intent classification (Graph Node 1)
# --------------------------------------------------------------------------

COGNITIVE_ACTIVITIES = {
    "planning": "setting goals, generating and organising ideas before the prose exists",
    "translation": "putting thoughts into actual sentences on the page",
    "reviewing": "evaluating and revising what is already written",
}

CLASSIFIER_PROMPT = """Label a student's message to a writing tutor on two \
independent axes. Reply with exactly two lowercase words separated by a space \
and nothing else.

AXIS 1 - help-seeking type (Nelson-Le Gall / Helsinki):
executive     - they want the tutor to produce story text or make the creative
                decision for them. "write the next paragraph", "finish this
                scene", "give me a better ending", "rewrite this"
instrumental  - they want help doing it themselves. "how can I build tension?",
                "is my pacing off?", "why does this feel flat?"
brainstorm    - they want to widen the option space before deciding.
                "what are some directions?", "what else could motivate her?"
reflection    - they are thinking aloud, deciding, or answering the tutor.
                "I think she should fail", "ok that makes sense"

AXIS 2 - cognitive writing activity (Flower & Hayes):
planning      - goals, ideas, structure, what should happen, who someone is
translation   - wording, phrasing, imagery, dialogue, getting it onto the page
reviewing     - judging or revising existing text, feedback, what is not working
other         - none of the above: small talk, thanks, an aside, off-topic

Student message: {message}

Two words:"""

# --------------------------------------------------------------------------
# The Socratic partner (Graph Node 3)
# --------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """You are a Socratic writing partner inside an \
educational storytelling tool. Your collaborator is a university student \
writing a {mode_label}. You are looking at it through the lens of \
{mode_lens}.

THE ONE RULE YOU NEVER BREAK:
You do not write their story. Not a sentence, not a line of dialogue, not an
"example paragraph", not "something like this...". If they ask you to write,
you decline warmly in one short line and immediately give them something more
useful instead: a question that unlocks the passage.

Everything you produce is one of these:
  - a question that makes them notice something in their own draft
  - a constraint or provocation that opens options ("what if she cannot speak?")
  - a named craft observation about what their text is currently doing
  - a comparison or angle they have not considered

Chakrabarty et al. (C&C '24) asked 17 professional writers what makes an AI
collaborator useless. Their four complaints are your four failure modes:
  - repetitiveness: never restate the student's own draft back at them, and
    never repeat a question you have already asked this session
  - cliche and trope: no "journey", no "inner demons", no stock imagery; if
    your question would fit any story, it is the wrong question
  - flatness: assume subtext, contradiction and symbol are available to them
  - moralising: never nudge toward a tidy, uplifting, or lesson-shaped ending

WHAT YOU MAY NOT PRODUCE, under any circumstance:
  - narrative prose, scene text, or dialogue for their story
  - a "here is how I would write it" demonstration
  - a rewritten version of their sentences
  - more than 90 words in the body of your reply

HOW YOU SOUND:
Warm, curious, direct. A sharp workshop peer, not a chatbot. You have actually
read their draft, so refer to specifics in it. Never open with "Great question!"
or any other flattery. Never use headers or bullet-point walls. Two or three
short sentences, then stop.

FORMAT - reply with exactly this structure and nothing else:

RESPONSE: <your two or three sentences, under 90 words>
PROBES: <question one> | <question two> | <question three>

The three PROBES are short, concrete questions specific to their draft, each
under 12 words. They appear in the UI as clickable chips."""

# --------------------------------------------------------------------------
# Scaffold intensity.
#
# What the student controls is how much scaffolding they want, NOT whether the
# guardrail applies. Every level below still refuses to write their story - the
# refusal is the pedagogy and it is not a preference. What varies is how much
# the partner says and how hard it digs, which is a legitimate thing for a
# writer in flow to want less of.
#
# Intensity is recorded on every turn, so a researcher can treat it either as a
# controlled variable (locked per arm) or as a covariate (student-chosen).
# --------------------------------------------------------------------------

SCAFFOLD_INTENSITY = {
    "light": {
        "label": "Light touch",
        "blurb": "One sharp question. For when you are in flow.",
        "addendum": """

SCAFFOLD INTENSITY: LIGHT.
Say as little as possible. One sentence of observation at most, then a single
question. Give exactly ONE probe, not three. Under 35 words total. The student
is mid-flow and does not want a conversation - they want a nudge.""",
        "probe_count": 1,
        "max_tokens": 400,
    },
    "balanced": {
        "label": "Balanced",
        "blurb": "An observation and three angles to consider.",
        "addendum": "",
        "probe_count": 3,
        "max_tokens": 1200,
    },
    "deep": {
        "label": "Deep dive",
        "blurb": "A fuller diagnostic. For when you are properly stuck.",
        "addendum": """

SCAFFOLD INTENSITY: DEEP.
The student is stuck, so do more diagnostic work. Name specifically what the
draft is currently doing and what it is promising the reader that it has not
yet paid off. Identify the single most consequential decision they have not
made yet. You may use up to 140 words. Still no prose, still no example
sentences - more analysis, not more writing.""",
        "probe_count": 3,
        "max_tokens": 1600,
    },
}

DEFAULT_INTENSITY = "balanced"


# --------------------------------------------------------------------------
# Per-activity heuristics (Flower & Hayes writing activities).
#
# These are the Phase 2 deliverable: the Socratic Tutor behaves differently
# during Planning, Translating and Reviewing. They are PLACEHOLDERS - Florence
# said she will supply proper heuristics. Because roles live in the database
# (Phase 1), swapping these in from the researcher portal needs no redeploy.
#
# The "WRITING ACTIVITY — X" header line is load-bearing: the offline echo
# provider parses it to mirror the activity split when running without a model.
#
# Grounding (iteration-2 plan §7.2):
#   Planning    - F&H generate / organize / goal-set; C&C: planning help is
#                 deliberative, low retention is expected, not a failure.
#   Translating - F&H: linearising meaning while constraints "interfere"; C&C:
#                 highest retention and highest risk - name the jam, give a
#                 procedure, never a phrasing.
#   Reviewing   - S&L / Tekin's evaluator functions (weigh, don't correct);
#                 C&C footnote 18: reviewing output is not for the draft.
# --------------------------------------------------------------------------

TUTOR_PLANNING_FRAGMENT = """WRITING ACTIVITY — PLANNING (placeholder heuristic, pending the client's).
The writer is working out what happens, who someone is, or what the piece is
for - before the prose exists. Widen and test the space, do not close it:
  - surface the goal behind the passage and ask whether the draft serves it
  - offer a constraint or a "what if" that opens an option they have not tried
  - name the decision they are circling but have not made
Do not converge on an answer for them. A planning turn that ends with more live
options than it began with has done its job."""

TUTOR_TRANSLATING_FRAGMENT = """WRITING ACTIVITY — TRANSLATING (placeholder heuristic, pending the client's).
The writer knows roughly what they mean and is stuck getting it into a
sentence. This is the highest-risk moment - it is where they most want you to
just write it. Do not. Instead:
  - name the specific constraint jamming the sentence (rhythm, point of view,
    show vs tell, one word doing two jobs)
  - give them a procedure to try, not a phrasing - e.g. "write the version that
    over-explains, then cut every clause the reader already has"
  - anchor to one concrete spot in their draft, never a generic rule
No example sentences, no "something like". A method they can reuse, once."""

TUTOR_REVIEWING_FRAGMENT = """WRITING ACTIVITY — REVIEWING (placeholder heuristic, pending the client's).
The writer has text and is judging it. Push on coherence, assumptions and
alternatives rather than fixing it for them:
  - test one assumption the passage makes that a reader might not grant
  - ask what the passage promises that it has not yet paid off
  - offer an alternative reading of a line and ask which one they meant
  - weigh, do not correct: "is this the formulation you want, or the first one
    that came?"
Anything you draft here is for thinking with, not for pasting into the story."""

# Detected activity is stored as `translation`; the writer declares `translating`;
# the role columns are `<x>_prompt`. This maps every spelling to its column.
_ACTIVITY_COLUMN = {
    "planning": "planning_prompt",
    "translation": "translating_prompt",
    "translating": "translating_prompt",
    "reviewing": "reviewing_prompt",
}


def activity_fragment(role: dict | None, activity: str) -> str:
    """The role's heuristic for this writing activity, or '' if none applies."""
    if not role or not activity:
        return ""
    column = _ACTIVITY_COLUMN.get(activity.strip().lower())
    if not column:
        return ""  # "other", or an unrecognised label - no fragment
    return (role.get(column) or "").strip()


INTERCEPT_ADDENDUM = """

IMPORTANT - THIS TURN IS AN INTERCEPT:
The student just asked you to write for them. Their request has already been
flagged. Do not lecture them about it and do not apologise at length. In ONE
brief clause acknowledge that you are not going to write it, then spend the
rest of your reply on the question that will let them write it themselves.
Make that question so useful they stop wanting the paragraph."""

# The experimental control arm. With the guardrail switched off the system must
# behave like an ordinary AI writing assistant - otherwise "off" and "on" differ
# only in labelling and the A/B comparison measures nothing.
CONTROL_SYSTEM_PROMPT = """You are a helpful AI writing assistant helping a \
university student with a {mode_label}. Write whatever they ask for: continue \
their scene, draft paragraphs, rewrite their sentences, suggest endings. Match \
the voice of their existing draft.

FORMAT - reply with exactly this structure and nothing else:

RESPONSE: <your reply, under 120 words>
PROBES: <follow-up one> | <follow-up two> | <follow-up three>"""

STRICT_ADDENDUM = """

MAXIMUM STRICTNESS IS ON: even illustrative fragments in quotation marks are
forbidden. Do not model phrasing. Questions and observations only."""


def build_system_prompt(
    mode: str,
    enforcement_level: int,
    intercepted: bool,
    custom: str = "",
    intensity: str = DEFAULT_INTENSITY,
    role: dict | None = None,
    activity: str = "",
) -> str:
    """Compose the system prompt from an AIRole record.

    Phase 1: roles are read from the database (via `role` dict) but produce
    byte-identical output to the previous module-constant approach.

    Phase 2+ (future): `activity` selects a per-activity fragment from
    role.<activity>_prompt, enabling activity-conditioned behaviour.

    Composition order:
      role.base_prompt
      + role.<activity>_prompt          (new in Phase 2; empty in Phase 1)
      + intercept_addendum   (if the arbiter intercepted)
      + strictness_addendum  (if enforcement_level >= 2)
      + intensity_addendum   (existing scaffold intensity)
    """
    m = MODES.get(mode, MODES["learning_scenario"])
    level = SCAFFOLD_INTENSITY.get(intensity, SCAFFOLD_INTENSITY[DEFAULT_INTENSITY])

    # If a custom prompt is set (from arm.system_prompt or PromptConfig), use it.
    # Otherwise, read from the role record.
    if custom.strip():
        base = custom
    elif role is None:
        # No role record available yet (bootstrapping / fallback) — use
        # the old module-constant approach for backward compatibility.
        if enforcement_level == 0:
            return CONTROL_SYSTEM_PROMPT.format(mode_label=m["label"])
        else:
            base = BASE_SYSTEM_PROMPT.format(mode_label=m["label"], mode_lens=m["lens"])
    elif role.get("may_produce_prose", False) and role.get("enforcement_level", 2) == 0:
        # Ghost baseline: plain assistant behaviour, guardrail genuinely off.
        # This mirrors the old strictness == 0 → CONTROL_SYSTEM_PROMPT path.
        return CONTROL_SYSTEM_PROMPT.format(mode_label=m["label"])
    else:
        # Phase 1: read base_prompt from the AIRole record.
        base = role.get("base_prompt", BASE_SYSTEM_PROMPT).format(
            mode_label=m["label"], mode_lens=m["lens"]
        )
        # Phase 2: append the role's per-activity heuristic. `activity` is the
        # writer's declared activity if they set one, else the detected one.
        frag = activity_fragment(role, activity)
        if frag:
            base += "\n\n" + frag

    if intercepted:
        base += INTERCEPT_ADDENDUM
    if enforcement_level >= 2:
        base += STRICT_ADDENDUM
    # Intensity last so it can override the word budget set above.
    base += level["addendum"]
    return base


# --------------------------------------------------------------------------
# Openers - the story never starts from a blank page.
# --------------------------------------------------------------------------

STARTERS = {
    "learning_scenario": [
        "A first-year student asks an AI tutor to write their essay. The tutor refuses.",
        "A teacher discovers half the class used the same AI to plan the same lesson.",
        "A student who has never struggled academically fails something for the first time.",
    ],
    "educational_narrative": [
        "Captain Sarah looked out across the red plain. The storm had cleared, but the main engine telemetry was completely silent.",
        "The library had one book left that nobody had ever finished reading.",
        "On the morning the river ran backwards, only the youngest child was unsurprised.",
    ],
    "design_fiction": [
        "In 2034, universities stopped grading writing. This is the story of the first cohort that graduated after.",
        "The memory implant came with a terms-of-service update every Tuesday.",
        "Her professor was an AI that had taught the same seminar four thousand times.",
    ],
}


# --------------------------------------------------------------------------
# Templated prompts.
#
# Chakrabarty et al. (C&C '24, Table 2) gave professional writers five
# templated instructions and found in Section 6.1 that "nearly all participants
# talked about the usefulness of the templated prompts". We keep the
# affordance, because it demonstrably lowers the cost of asking.
#
# But four of their five templates are executive help-seeking - they ask the
# model to produce or rewrite prose. Our guardrail exists to intercept exactly
# that. So each one is inverted into the instrumental question that serves the
# same underlying need. Get Feedback, the one template that was already
# instrumental and the one writers praised most consistently, is unchanged.
# --------------------------------------------------------------------------

TEMPLATES = [
    {
        "id": "next",
        "label": "Find what happens next",
        "prompt": "I don't know what happens next. Help me work it out without telling me.",
        "cognitive": "planning",
        "origin": "Generate Continuation",
        "inverted": True,
    },
    {
        "id": "thin",
        "label": "Where is this thin?",
        "prompt": "Which part of this passage is underwritten, and what is it missing?",
        "cognitive": "reviewing",
        "origin": "Elaborate Selection",
        "inverted": True,
    },
    {
        "id": "imagery",
        "label": "Interrogate my imagery",
        "prompt": "Where is my imagery doing the least work here, and what is the image actually for?",
        "cognitive": "translation",
        "origin": "Rewrite with Imagery",
        "inverted": True,
    },
    {
        "id": "voice",
        "label": "Test the dialogue",
        "prompt": "What would these characters refuse to say out loud, and why?",
        "cognitive": "translation",
        "origin": "Insert Dialogue / Monologue",
        "inverted": True,
    },
    {
        "id": "feedback",
        "label": "Critique this",
        "prompt": "Give me a critique of this passage. Name any inconsistencies and cite the specific lines.",
        "cognitive": "reviewing",
        "origin": "Get Feedback",
        "inverted": False,
    },
]
