"""Story workspace CRUD + the story-starter catalogue."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import prompts
from ..db import get_db
from ..deps import current_user_id, resolve_user
from ..metrics import agency_report
from ..models import ConversationTurn, StoryWorkspace, TelemetryEvent, User
from ..schemas import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def current_user(db: Session, user_id: str | None = None) -> User:
    return resolve_user(db, user_id, "student")


def _serialize(ws: StoryWorkspace, db: Session) -> WorkspaceOut:
    ai_texts = [
        t.message_text for t in db.scalars(
            select(ConversationTurn).where(
                ConversationTurn.workspace_id == ws.workspace_id,
                ConversationTurn.speaker == "ai",
            )
        )
    ]
    report = agency_report(ws.current_content, ai_texts)
    count = len(list(db.scalars(
        select(ConversationTurn).where(ConversationTurn.workspace_id == ws.workspace_id)
    )))
    owner = db.get(User, ws.user_id)
    return WorkspaceOut(
        workspace_id=ws.workspace_id,
        title=ws.title,
        initial_prompt=ws.initial_prompt,
        current_content=ws.current_content,
        mode=ws.mode,
        status=ws.status,
        created_at=ws.created_at.isoformat(),
        updated_at=ws.updated_at.isoformat(),
        word_count=report["total_words"],
        agency_ratio=report["agency_ratio"],
        ai_retention=report["ai_retention_rouge_l"],
        scaffold_intensity=ws.scaffold_intensity,
        turn_count=count,
        owner=owner.display_name if owner else "",
    )


@router.get("/modes")
def list_modes():
    return {
        "modes": [
            {"id": k, "label": v["label"], "blurb": v["blurb"],
             "starters": prompts.STARTERS.get(k, [])}
            for k, v in prompts.MODES.items()
        ]
    }


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db), user_id: str | None = Depends(current_user_id)
):
    user = current_user(db, user_id)
    rows = db.scalars(
        select(StoryWorkspace)
        .where(StoryWorkspace.user_id == user.user_id)
        .order_by(StoryWorkspace.updated_at.desc())
    )
    return [_serialize(w, db) for w in rows]


@router.post("", response_model=WorkspaceOut)
def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    user_id: str | None = Depends(current_user_id),
):
    user = current_user(db, user_id)
    ws = StoryWorkspace(
        user_id=user.user_id,
        title=body.title or "Untitled Story",
        initial_prompt=body.initial_prompt,
        current_content=body.initial_prompt,
        mode=body.mode,
        scaffold_intensity=body.scaffold_intensity,
        arm_id=user.arm_id,
    )
    db.add(ws)
    db.add(TelemetryEvent(
        workspace_id=ws.workspace_id, user_id=user.user_id, event_type="session_start",
        payload={"mode": body.mode, "seeded": bool(body.initial_prompt),
                 "arm_id": user.arm_id, "intensity": body.scaffold_intensity},
    ))
    db.commit()
    db.refresh(ws)
    return _serialize(ws, db)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, db: Session = Depends(get_db)):
    ws = db.get(StoryWorkspace, workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    return _serialize(ws, db)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(workspace_id: str, body: WorkspaceUpdate, db: Session = Depends(get_db)):
    ws = db.get(StoryWorkspace, workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(ws, field, value)
    db.commit()
    db.refresh(ws)
    return _serialize(ws, db)


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str, db: Session = Depends(get_db)):
    ws = db.get(StoryWorkspace, workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    db.delete(ws)
    db.commit()
    return {"ok": True}


@router.get("/{workspace_id}/turns")
def list_turns(workspace_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.workspace_id == workspace_id)
        .order_by(ConversationTurn.timestamp)
    )
    return [
        {
            "turn_id": t.turn_id, "speaker": t.speaker, "message_text": t.message_text,
            "intent_type": t.intent_type, "cognitive_activity": t.cognitive_activity,
            "intercepted": t.intercepted,
            "node_path": t.node_path, "suggestions": t.suggestions,
            "provider": t.provider, "model_name": t.model_name,
            "scaffold_intensity": t.scaffold_intensity,
            "latency_ms": t.latency_ms, "timestamp": t.timestamp.isoformat(),
        }
        for t in rows
    ]
