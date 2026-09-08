"""The co-creative turn endpoint.

Streams the graph's progress as Server-Sent Events. The progressive reveal is
deliberate: the interface shows the Helsinki filter firing *before* the answer
arrives, which is what makes the pedagogy legible rather than magical.
"""
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..graph import TurnState
from ..graph.nodes import (
    agency_enforcer,
    role_arbiter,
    intent_classifier,
    response_formatter,
    response_engine,
)
from ..graph.runner import GRAPH_SPEC
from ..models import (
    AIRole, ConversationTurn, ExperimentArm, PromptConfig, StoryWorkspace, TelemetryEvent, User,
)
from ..prompts import DEFAULT_INTENSITY, SCAFFOLD_INTENSITY
from .experiments import default_arm, ensure_default_roles
from ..schemas import TurnRequest

router = APIRouter(prefix="/api", tags=["chat"])

_NODES = [
    ("intent_classifier", intent_classifier),
    ("role_arbiter", role_arbiter),
    ("response_engine", response_engine),
    ("response_formatter", response_formatter),
    ("agency_enforcer", agency_enforcer),
]


def _active_config(db: Session) -> PromptConfig | None:
    return db.scalar(select(PromptConfig).where(PromptConfig.active_flag.is_(True)))


def _role_dict(role: AIRole) -> dict:
    """The subset of an AIRole the graph needs, as a plain dict (no ORM state)."""
    return {
        "role_id": role.role_id,
        "archetype": role.archetype,
        "behaviour": role.behaviour,
        "base_prompt": role.base_prompt,
        "planning_prompt": role.planning_prompt,
        "translating_prompt": role.translating_prompt,
        "reviewing_prompt": role.reviewing_prompt,
        "may_produce_prose": role.may_produce_prose,
        "enforcement_level": role.enforcement_level,
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Browsers hold a fetch() stream shut until enough bytes have arrived to cross
# an internal flush threshold. Our node events are ~60 bytes each, so without
# this the whole graph's progress lands in one burst at the end and the live
# pipeline never animates. A 2KB comment preamble opens the stream immediately;
# lines starting with ':' are comments and are ignored by SSE consumers.
_SSE_PREAMBLE = ":" + " " * 2048 + "\n\n"


@router.get("/graph")
def graph_spec():
    return {"nodes": GRAPH_SPEC}


@router.post("/workspaces/{workspace_id}/turn")
async def take_turn(workspace_id: str, body: TurnRequest, db: Session = Depends(get_db)):
    ws = db.get(StoryWorkspace, workspace_id)
    if not ws:
        return {"error": "Workspace not found"}

    # Keep the draft authoritative on the server before reasoning about it.
    if body.draft and body.draft != ws.current_content:
        ws.current_content = body.draft
        db.commit()

    history = [
        {"speaker": t.speaker, "text": t.message_text}
        for t in db.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.workspace_id == workspace_id)
            .order_by(ConversationTurn.timestamp)
        )
    ]

    cfg = _active_config(db)

    # Resolution order: the condition this workspace was created under, then the
    # participant's assignment, then the default condition. There is no separate
    # "global config" any more - everything is a condition.
    owner = db.get(User, ws.user_id)
    arm = db.get(ExperimentArm, ws.arm_id) if ws.arm_id else None
    if arm is None and owner and owner.arm_id:
        arm = db.get(ExperimentArm, owner.arm_id)
    if arm is None:
        arm = default_arm(db)

    # Phase 1: resolve the AIRole from the arm. Arms are back-filled with a
    # role_id on every read path, so this normally hits; the fallback only
    # matters for an arm mutated to an empty role_id mid-request.
    role = db.get(AIRole, arm.role_id) if (arm and arm.role_id) else None
    if role is None:
        seeded = ensure_default_roles(db)
        role = seeded["ghost"] if (arm and arm.guardrail_strictness == 0) else seeded["tutor"]

    provider = (arm.provider if arm else "") or (cfg.provider if cfg else "")
    model = (arm.model_name if arm else "") or (cfg.model_name if cfg else "")
    temperature = arm.temperature if arm else (cfg.temperature if cfg else 0.8)
    system_prompt = (arm.system_prompt if arm else "") or (cfg.system_prompt if cfg else "")
    intensity = (arm.scaffold_intensity if arm else None) or ws.scaffold_intensity or DEFAULT_INTENSITY

    # Student-supplied overrides are honoured only where the condition permits.
    if body.intensity and body.intensity in SCAFFOLD_INTENSITY:
        if arm is None or arm.allow_student_intensity:
            intensity = body.intensity
    if body.provider:
        allowed = (arm.allowed_providers or []) if arm else []
        if arm is None or (arm.allow_student_model and body.provider in allowed):
            provider = body.provider
            model = body.model or ""

    state = TurnState(
        message=body.message,
        draft=ws.current_content,
        selection=body.selection,
        mode=ws.mode,
        history=history,
        provider_name=provider,
        model_override=model,
        temperature=temperature,
        max_tokens=cfg.max_tokens if cfg else 1200,
        strictness=role.enforcement_level,
        # Phase 1 role-based fields. role_version_id pins the turn to this exact
        # role row; because edits are append-only, that row never changes.
        role_id=role.role_id,
        role=_role_dict(role),
        role_version_id=role.role_id,
        enforcement_level=role.enforcement_level,
        may_produce_prose=role.may_produce_prose,
        declared_activity=body.declared_activity or "",
        custom_system_prompt=system_prompt,
        intensity=intensity,
        arm_id=arm.arm_id if arm else "",
    )
    user_id = ws.user_id
    mode = ws.mode

    async def stream():
        nonlocal state
        yield _SSE_PREAMBLE
        yield _sse("start", {"workspace_id": workspace_id})

        for node_id, fn in _NODES:
            yield _sse("node", {"id": node_id, "status": "running"})
            state = await fn(state)
            extra = {}
            if node_id == "intent_classifier":
                extra = {"intent": state.intent, "cognitive": state.cognitive}
            elif node_id == "role_arbiter":
                extra = {"intercepted": state.intercepted}
            elif node_id == "agency_enforcer":
                extra = {"enforcement": state.enforcement}
            yield _sse("node", {"id": node_id, "status": "done", **extra})
            await asyncio.sleep(0)  # let the event flush

        # Persist both sides of the exchange plus the telemetry trail.
        with SessionLocal() as s:
            user_turn = ConversationTurn(
                workspace_id=workspace_id, speaker="user", message_text=body.message,
                intent_type=state.intent, cognitive_activity=state.cognitive,
                intercepted=state.intercepted, arm_id=state.arm_id,
                role_version_id=state.role_version_id,
                scaffold_intensity=state.intensity,
            )
            ai_turn = ConversationTurn(
                workspace_id=workspace_id, speaker="ai", message_text=state.response_text,
                intent_type=state.intent, cognitive_activity=state.cognitive,
                intercepted=state.intercepted, node_path=state.node_path, suggestions=state.probes,
                model_name=state.model_name, provider=state.provider_used,
                arm_id=state.arm_id, role_version_id=state.role_version_id,
                scaffold_intensity=state.intensity,
                latency_ms=state.latency_ms,
            )
            s.add_all([user_turn, ai_turn])
            s.add(TelemetryEvent(
                workspace_id=workspace_id, user_id=user_id, event_type="prompt",
                duration_ms=state.latency_ms,
                payload={"intent": state.intent, "cognitive": state.cognitive,
                         "intercepted": state.intercepted, "message": body.message,
                         "mode": mode, "scoped_to_selection": bool(body.selection.strip()),
                         "arm_id": state.arm_id, "intensity": state.intensity},
            ))
            s.add(TelemetryEvent(
                workspace_id=workspace_id, user_id=user_id, event_type="ai_response",
                duration_ms=state.latency_ms,
                payload={"provider": state.provider_used, "model": state.model_name,
                         "node_path": state.node_path, "enforcement": state.enforcement,
                         "probes": state.probes},
            ))
            if state.intercepted:
                s.add(TelemetryEvent(
                    workspace_id=workspace_id, user_id=user_id, event_type="intercept",
                    payload={"original_request": body.message, "intent": state.intent},
                ))
            s.commit()
            turn_id = ai_turn.turn_id

        yield _sse("done", {
            "turn_id": turn_id,
            "response_text": state.response_text,
            "probes": state.probes,
            "intent": state.intent,
            "cognitive": state.cognitive,
            "intensity": state.intensity,
            "intercepted": state.intercepted,
            "node_path": state.node_path,
            "enforcement": state.enforcement,
            "provider": state.provider_used,
            "model_name": state.model_name,
            "latency_ms": state.latency_ms,
            "error": state.error,
        })

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
