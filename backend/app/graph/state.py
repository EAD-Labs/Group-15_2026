"""State object threaded through the graph. One instance per conversation turn."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnState:
    # inputs
    message: str
    draft: str
    mode: str
    # Text the student highlighted in the editor, if the ask is about a span
    # rather than the whole draft (paper 3.2).
    selection: str = ""
    history: list[dict] = field(default_factory=list)
    provider_name: str = "gemini"
    model_override: str = ""
    temperature: float = 0.8
    max_tokens: int = 1200
    strictness: int = 2
    # Phase 1: role-based fields replacing strictness
    role_id: str = ""
    role: dict | None = None  # The AIRole record, loaded in chat.py
    role_version_id: str = ""
    enforcement_level: int = 2
    may_produce_prose: bool = False
    # Iteration 2's student-declared activity. No longer offered in the UI and
    # no longer consulted; still stored if a client sends it, for old data.
    declared_activity: str = ""
    # The activity that conditions the prompt. Since iteration 3 this is always
    # the Monitor's decision (graph/monitor.py), never the student's.
    effective_activity: str = ""
    custom_system_prompt: str = ""
    intensity: str = "balanced"
    goals: str = ""  # the writer's stated goal for the piece, if any
    notes: str = ""  # the writer's brief idea / journal for the story, if any
    arm_id: str = ""

    # Monitor inputs, read from the previous turn in this story.
    draft_words: int = 0
    prev_draft_words: int | None = None
    prev_activity: str = ""
    # In-flight LLM judgement for the Monitor, started alongside the classifier.
    monitor_task: Any = None

    # produced along the way
    intent: str = ""
    cognitive: str = ""
    activity_evidence: dict = field(default_factory=dict)
    intercepted: bool = False
    system_prompt: str = ""
    user_prompt: str = ""
    raw_reply: str = ""
    response_text: str = ""
    probes: list[str] = field(default_factory=list)
    enforcement: list[str] = field(default_factory=list)

    # instrumentation
    node_path: list[str] = field(default_factory=list)
    model_name: str = ""
    provider_used: str = ""
    latency_ms: int = 0
    error: str = ""

    def visit(self, node: str) -> None:
        self.node_path.append(node)
