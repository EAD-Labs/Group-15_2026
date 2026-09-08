"""Request / response contracts."""
from pydantic import BaseModel, Field


class SessionIn(BaseModel):
    display_name: str = ""
    role: str = "student"


class UserOut(BaseModel):
    user_id: str
    display_name: str
    role: str
    participant_code: str
    arm_id: str = ""


class ArmIn(BaseModel):
    name: str | None = None
    description: str | None = None
    provider: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    guardrail_strictness: int | None = None
    role_id: str | None = None
    scaffold_intensity: str | None = None
    system_prompt: str | None = None
    allow_student_intensity: bool | None = None
    allow_student_model: bool | None = None
    allowed_providers: list[str] | None = None
    is_control: bool | None = None
    is_default: bool | None = None
    active: bool | None = None


class ArmOut(BaseModel):
    arm_id: str
    name: str
    description: str
    provider: str
    model_name: str
    temperature: float
    guardrail_strictness: int
    role_id: str = ""
    role_name: str | None = None
    scaffold_intensity: str
    system_prompt: str
    allow_student_intensity: bool
    allow_student_model: bool
    allowed_providers: list[str]
    is_control: bool
    is_default: bool
    active: bool
    participants: int = 0


class RoleIn(BaseModel):
    name: str | None = None
    archetype: str | None = None
    behaviour: str | None = None
    base_prompt: str | None = None
    planning_prompt: str | None = None
    translating_prompt: str | None = None
    reviewing_prompt: str | None = None
    may_produce_prose: bool | None = None
    enforcement_level: int | None = None


class RoleOut(BaseModel):
    role_id: str
    name: str
    archetype: str
    behaviour: str
    base_prompt: str
    planning_prompt: str
    translating_prompt: str
    reviewing_prompt: str
    may_produce_prose: bool
    enforcement_level: int
    version: int
    parent_role_id: str
    created_at: str


class AssignIn(BaseModel):
    user_id: str = ""
    arm_id: str = ""
    randomise: bool = False
    include_assigned: bool = False
    seed: int | None = None


class WorkspaceCreate(BaseModel):
    title: str = "Untitled Story"
    initial_prompt: str = ""
    mode: str = "learning_scenario"
    scaffold_intensity: str = "balanced"


class WorkspaceUpdate(BaseModel):
    title: str | None = None
    current_content: str | None = None
    mode: str | None = None
    status: str | None = None
    scaffold_intensity: str | None = None


class WorkspaceOut(BaseModel):
    workspace_id: str
    title: str
    initial_prompt: str
    current_content: str
    mode: str
    status: str
    created_at: str
    updated_at: str
    word_count: int = 0
    agency_ratio: float = 1.0
    ai_retention: float = 0.0
    turn_count: int = 0
    owner: str = ""
    scaffold_intensity: str = "balanced"


class TurnRequest(BaseModel):
    message: str
    draft: str = ""
    selection: str = ""
    provider: str = ""
    model: str = ""
    intensity: str = ""
    # Flower & Hayes "Monitor": the writer's own declaration of what they are
    # doing right now. Stored alongside the detected activity; not yet used to
    # condition behaviour (that is Phase 2).
    declared_activity: str = ""


class TurnOut(BaseModel):
    turn_id: str
    response_text: str
    probes: list[str]
    intent: str
    cognitive: str = ""
    intensity: str = ""
    intercepted: bool
    node_path: list[str]
    enforcement: list[str]
    provider: str
    model_name: str
    latency_ms: int
    error: str = ""


class EventIn(BaseModel):
    workspace_id: str = ""
    event_type: str
    delta_change: int = 0
    duration_ms: int = 0
    payload: dict = Field(default_factory=dict)


class ConfigIn(BaseModel):
    label: str | None = None
    provider: str | None = None
    model_name: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    guardrail_strictness: int | None = None
