"""State object threaded through the graph. One instance per conversation turn."""
from dataclasses import dataclass, field


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
    declared_activity: str = ""  # writer's Monitor declaration
    custom_system_prompt: str = ""
    intensity: str = "balanced"
    arm_id: str = ""

    # produced along the way
    intent: str = ""
    cognitive: str = ""
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
