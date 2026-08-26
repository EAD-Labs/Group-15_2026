"""Data entities. These mirror HLD 8.2 field-for-field.

User | StoryWorkspace | ConversationTurn | TelemetryEvent | PromptConfig
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentArm(Base):
    """One condition in a study.

    Everything a researcher might vary lives here, so "we changed X and
    students did Y" is answerable by joining outcomes back to an arm rather
    than by remembering what the config looked like last Tuesday.
    """
    __tablename__ = "experiment_arms"

    arm_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, default="Untitled condition")
    description: Mapped[str] = mapped_column(Text, default="")

    provider: Mapped[str] = mapped_column(String, default="gemini")
    model_name: Mapped[str] = mapped_column(String, default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.8)
    guardrail_strictness: Mapped[int] = mapped_column(Integer, default=2)
    scaffold_intensity: Mapped[str] = mapped_column(String, default="balanced")
    system_prompt: Mapped[str] = mapped_column(Text, default="")

    # Which knobs the student may touch in this condition. Locking them makes
    # the arm a controlled variable; unlocking makes it a logged covariate.
    allow_student_intensity: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_student_model: Mapped[bool] = mapped_column(Boolean, default=False)
    # Providers a student may pick from when allow_student_model is on.
    allowed_providers: Mapped[list] = mapped_column(JSON, default=list)

    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    # Where unassigned participants land. Exactly one condition holds this.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # Pseudonymised handle - HLD 11.4 asks for minimal identification.
    display_name: Mapped[str] = mapped_column(String, default="Student")
    role: Mapped[str] = mapped_column(String, default="student")  # student | researcher
    email: Mapped[str] = mapped_column(String, default="")
    participant_code: Mapped[str] = mapped_column(String, default="Participant_01")
    arm_id: Mapped[str] = mapped_column(String, default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    workspaces: Mapped[list["StoryWorkspace"]] = relationship(back_populates="user")


class StoryWorkspace(Base):
    __tablename__ = "story_workspaces"

    workspace_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    title: Mapped[str] = mapped_column(String, default="Untitled Story")
    initial_prompt: Mapped[str] = mapped_column(Text, default="")
    current_content: Mapped[str] = mapped_column(Text, default="")
    # learning_scenario | educational_narrative | design_fiction  (client brief, p3)
    mode: Mapped[str] = mapped_column(String, default="learning_scenario")
    status: Mapped[str] = mapped_column(String, default="active")
    # Snapshotted at creation so re-assigning a participant never rewrites
    # the condition their existing work was produced under.
    arm_id: Mapped[str] = mapped_column(String, default="", index=True)
    scaffold_intensity: Mapped[str] = mapped_column(String, default="balanced")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="workspaces")
    turns: Mapped[list["ConversationTurn"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    turn_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("story_workspaces.workspace_id"))
    speaker: Mapped[str] = mapped_column(String)  # user | ai
    message_text: Mapped[str] = mapped_column(Text)
    # executive_help | instrumental_help | brainstorming | reflection  (HLD 6.1 Module 2)
    intent_type: Mapped[str] = mapped_column(String, default="")
    # planning | translation | reviewing  (Flower & Hayes cognitive process
    # model, as operationalised by Chakrabarty et al. C&C '24)
    cognitive_activity: Mapped[str] = mapped_column(String, default="")
    intercepted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ordered list of graph nodes this turn actually traversed.
    node_path: Mapped[list] = mapped_column(JSON, default=list)
    suggestions: Mapped[list] = mapped_column(JSON, default=list)
    model_name: Mapped[str] = mapped_column(String, default="")
    provider: Mapped[str] = mapped_column(String, default="")
    # Condition and intensity in force for this specific turn.
    arm_id: Mapped[str] = mapped_column(String, default="", index=True)
    scaffold_intensity: Mapped[str] = mapped_column(String, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)

    workspace: Mapped[StoryWorkspace] = relationship(back_populates="turns")


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String, index=True, default="")
    user_id: Mapped[str] = mapped_column(String, index=True, default="")
    # keystroke | paste | prompt | ai_response | intercept | export |
    # config_change | suggestion_adopted | session_start
    event_type: Mapped[str] = mapped_column(String, index=True)
    delta_change: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class PromptConfig(Base):
    """Researcher-editable experiment configuration (HLD 6.1 Module 3, UC-05)."""
    __tablename__ = "prompt_configs"

    config_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String, default="Default Socratic Scaffold")
    provider: Mapped[str] = mapped_column(String, default="gemini")
    model_name: Mapped[str] = mapped_column(String, default="gemini-3.6-flash")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.8)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1200)
    # 0 = permissive, 1 = balanced, 2 = strict (never emit prose, ever)
    guardrail_strictness: Mapped[int] = mapped_column(Integer, default=2)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
