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

_CRAFT = [
    "Right now the tension sits in the situation rather than in anyone's choice.",
    "Your draft is telling us the stakes; it hasn't yet made us feel them arrive.",
    "There's a gap between what your character knows and what the reader knows - that gap is usable.",
    "The scene is holding its detail at arm's length. The specifics are where belief comes from.",
]

_PROBE_BANK = [
    "What does your character want in this exact moment?",
    "What would make this harder in an interesting way?",
    "Who else is affected by what just happened?",
    "What is the worst thing that could interrupt now?",
    "What detail would only this character notice?",
    "What is your character refusing to admit?",
    "Where would a reader stop believing this?",
    "What happens if the obvious solution fails?",
    "What does this scene need to teach the reader?",
    "Which sentence here are you least sure about?",
]

_EMPTY_PROBES = [
    "Who is at the centre of this, and what do they want?",
    "Where and when does the first scene open?",
    "What goes wrong in the first two minutes?",
]


class EchoProvider(LLMProvider):
    name = "echo"

    def __init__(self, model: str = "offline-socratic-v1"):
        self.model = model

    async def complete(self, system, user, temperature=0.8, max_tokens=600) -> LLMReply:
        # Classification requests get a keyword verdict so the Helsinki filter
        # still discriminates all four intents when running fully offline.
        if "Student message:" in user and "Two words:" in user:
            return LLMReply(text=self._classify(user), model=self.model, provider=self.name)

        rng = random.Random(hash(user) & 0xFFFF)

        # Control arm: the guardrail is off, so behave like an ordinary
        # assistant. Kept deliberately flat - the point of the control is that
        # the student stops thinking, not that the prose is good.
        if "Write whatever they ask for" in system:
            return LLMReply(
                text=(
                    "RESPONSE: She moved toward the rover without waiting for the "
                    "telemetry to resolve. Whatever the storm had taken, the answer "
                    "would be inside the housing, and there was no version of this "
                    "where she waited for permission.\n"
                    "PROBES: Want me to continue? | Should I lengthen this? | "
                    "Want a different ending?"
                ),
                model=self.model, provider=self.name,
            )

        intercepted = "THIS TURN IS AN INTERCEPT" in system

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
        else:
            opening = rng.choice(_OPENINGS_INTERCEPT if intercepted else _OPENINGS_NORMAL)
            body = f"{opening} {rng.choice(_CRAFT)}"
            probes = rng.sample(_PROBE_BANK, 3)

        text = "RESPONSE: " + body + "\nPROBES: " + " | ".join(probes)
        return LLMReply(text=text, model=self.model, provider=self.name)

    @staticmethod
    def _classify(user: str) -> str:
        """Return both axis labels, matching the live classifier's contract."""
        m = re.search(r"Student message:\s*(.*?)\n\nTwo words:", user, re.S)
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
        else:
            cognitive = "planning"

        return f"{help_type} {cognitive}"

    async def health(self):
        return True, "Ready (deterministic offline mode)"
