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
    strictness: int,
    intercepted: bool,
    custom: str = "",
    intensity: str = DEFAULT_INTENSITY,
) -> str:
    m = MODES.get(mode, MODES["learning_scenario"])
    level = SCAFFOLD_INTENSITY.get(intensity, SCAFFOLD_INTENSITY[DEFAULT_INTENSITY])

    if custom.strip():
        base = custom
    elif strictness == 0:
        # Control condition: a plain assistant, guardrail genuinely disabled.
        return CONTROL_SYSTEM_PROMPT.format(mode_label=m["label"])
    else:
        base = BASE_SYSTEM_PROMPT.format(mode_label=m["label"], mode_lens=m["lens"])

    if intercepted:
        base += INTERCEPT_ADDENDUM
    if strictness >= 2:
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
