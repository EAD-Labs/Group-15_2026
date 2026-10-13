"""Deterministic offline provider.

Not a toy: this is the demo's insurance policy. With no API key, no network and
no Ollama model, the application still runs end to end and every interaction-
design claim in the HLD stays demonstrable. It composes real Socratic moves
from the draft itself rather than calling a model.
"""
import random
import re

from .base import LLMProvider, LLMReply

_OPENINGS_INTERCEPT = [
    "I'm not going to write that part - it's the part that's actually yours.",
    "That paragraph is the one worth struggling over, so I'll leave it to you.",
    "Writing it for you would skip the useful bit. Let's find the way in instead.",
]

_OPENINGS_NORMAL = [
    "Here's what I notice in what you have so far.",
    "Something in your draft is already doing work you might not have clocked.",
    "Let's look at what the text is currently promising the reader.",
]

# Observations, not directions. The earlier lines here nudged every story the
# same way ("make it harder", "what does this need to teach the reader?") -
# exactly the content-steering Florence flagged under H7.
_CRAFT = [
    "Some of what you want the reader to understand is on the page, and some is still in your head.",
    "The draft has set up a situation; what it means for the people in it is still open.",
    "There's a gap between what your character knows and what the reader knows.",
    "Parts of the scene are told in summary and parts are shown moment by moment.",
]

_PROBE_BANK = [
    "What does your character want in this exact moment?",
    "Who else is affected by what just happened?",
    "What detail would only this character notice?",
    "Where would a reader stop believing this?",
    "Which sentence here are you least sure about?",
    "What do you want the reader to feel at the end of this paragraph?",
    "Which direction for the next scene feels most like your story?",
]

_EMPTY_PROBES = [
    "Who is at the centre of this, and what do they want?",
    "Where and when does the first scene open?",
    "What goes wrong in the first two minutes?",
]

# Phase 2: when the system prompt carries a per-activity heuristic (its header
# line is "WRITING ACTIVITY — X"), the offline provider mirrors the split so the
# activity-conditioned behaviour is demonstrable with no model.
_ACTIVITY_MOVES = {
    "planning": (
        "Before the prose, there's a decision here you haven't committed to.",
        [
            "What does this scene need to be true by the end?",
            "What's the version of this you're avoiding?",
            "Who wants something here, and what stands in the way?",
            "What would you cut if you could only keep one thread?",
        ],
    ),
    "translating": (
        "The meaning is clear enough; the sentence is fighting you on how to carry it.",
        [
            "Which clause is the reader already ahead of?",
            "What is this sentence doing that a shorter one couldn't?",
            "Say it aloud — where does the rhythm stumble?",
            "Which word here is being asked to do two jobs?",
        ],
    ),
    "reviewing": (
        "You have the text; the question is what it's quietly assuming.",
        [
            "What does this passage promise that it hasn't paid off?",
            "Which assumption here would a sceptical reader not grant?",
            "Is this the phrasing you want, or the first one that came?",
            "What would you lose by cutting this paragraph entirely?",
        ],
    ),
}


class EchoProvider(LLMProvider):
    name = "echo"

    def __init__(self, model: str = "offline-socratic-v1"):
        self.model = model

    async def complete(self, system, user, temperature=0.8, max_tokens=600) -> LLMReply:
        # Classification requests get a keyword verdict so the Helsinki filter
        # still discriminates all four intents when running fully offline.
        if "Student message:" in user and ("Three words:" in user or "Two words:" in user):
            return LLMReply(text=self._classify(user), model=self.model, provider=self.name)

        rng = random.Random(hash(user) & 0xFFFF)

        # Control arm: the guardrail is off, so behave like an ordinary
        # assistant. Kept deliberately flat - the point of the control is that
        # the student stops thinking, not that the prose is good.
        if "Write whatever they ask for" in system:
            # It used to return a fixed paragraph about a rover, whatever the
            # student's story was - fabricated "AI prose" in the control arm's
            # data whenever the real model failed (review hole 7).
            return LLMReply(
                text=(
                    "RESPONSE: The writing assistant can't generate text while "
                    "running offline.\nPROBES: "
                ),
                model=self.model, provider=self.name,
            )

        if "Reply with your answer only" in system:
            return LLMReply(text=self._v2(system, user, rng), model=self.model, provider=self.name)

        intercepted = "THIS TURN IS AN INTERCEPT" in system

        activity = ""
        ma = re.search(r"WRITING ACTIVITY [—-] (\w+)", system)
        if ma:
            activity = ma.group(1).strip().lower()

        draft = ""
        m = re.search(r"STORY DRAFT SO FAR:\n(.*?)(?:\n---|\Z)", user, re.S)
        if m:
            draft = m.group(1).strip()
        words = len(draft.split())

        if words < 15:
            body = (
                "You have the beginning of an idea and not much anchoring it yet. "
                "Before the prose, decide who this belongs to."
            )
            probes = list(_EMPTY_PROBES)
        elif activity in _ACTIVITY_MOVES and not intercepted:
            lead, bank = _ACTIVITY_MOVES[activity]
            body = f"{lead} {rng.choice(_CRAFT)}"
            probes = rng.sample(bank, 3)
        else:
            opening = rng.choice(_OPENINGS_INTERCEPT if intercepted else _OPENINGS_NORMAL)
            body = f"{opening} {rng.choice(_CRAFT)}"
            probes = rng.sample(_PROBE_BANK, 3)

        text = "RESPONSE: " + body + "\nPROBES: " + " | ".join(probes)
        return LLMReply(text=text, model=self.model, provider=self.name)

    @staticmethod
    def _v2(system: str, user: str, rng: random.Random) -> str:
        """Response contract v2, offline: plain text, at most one question,
        and honest about what a model-free scaffold cannot do."""
        if "THIS REQUEST HAS A DIRECT ANSWER" in system:
            return ("I can't look that up while running offline. A dictionary or "
                    "grammar reference will give you the exact answer.")
        if "THEY ASKED YOU TO WRITE OR REWRITE" in system:
            return ("That wording should come from you. Say what the sentence has to "
                    "do for the reader, then write the plainest version that does it. "
                    "What does it have to carry?")
        if "THE DIRECTION IS OPEN" in system:
            return ("There are several ways this could go: what changes for the main "
                    "character next, what someone else wants from them, or what the "
                    "reader still doesn't know. Which of these matters most to you?")
        return f"{rng.choice(_CRAFT)} {rng.choice(_PROBE_BANK)}"

    @staticmethod
    def _classify(user: str) -> str:
        """Return all three axis labels, matching the live classifier's contract."""
        m = re.search(r"Student message:\s*(.*?)\n\n(?:Three|Two) words:", user, re.S)
        msg = (m.group(1) if m else user).lower().strip()

        if re.search(r"\b(what if|what are some|other ways|alternatives?|directions|options|brainstorm|ideas)\b", msg):
            help_type = "brainstorm"
        elif re.search(r"^(i think|i want|i'?ll|i am|i'?m|maybe|ok|okay|yes|no|right|got it|she |he |they )", msg):
            help_type = "reflection"
        else:
            help_type = "instrumental"

        if re.search(r"\b(word|phrase|sentence|line|imagery|image|metaphor|dialogue|voice|tone|describ|prose|phrasing|rewrite|rephrase)\b", msg):
            cognitive = "translation"
        elif re.search(r"\b(feedback|critique|inconsisten|work(s|ing|ed)?\b|flat|weak|wrong|fix|revise|cut|improve|better|repetit|thin|underwritten|pulling its weight)\b", msg):
            cognitive = "reviewing"
        elif re.search(r"\b(what if|happens? next|should happen|idea|direction|option|plot|charact|motivat|structur|arc|ending|begin|start|outline|goal)\b", msg):
            cognitive = "planning"
        else:
            cognitive = "other"

        if re.search(r"\bspell|\bgrammar|\bpunctuat|\bwhat does .{1,40} mean\b|\bmeaning of\b", msg):
            form = "direct"
        else:
            form = "open"

        return f"{help_type} {cognitive} {form}"

    async def health(self):
        return True, "Ready (deterministic offline mode)"
