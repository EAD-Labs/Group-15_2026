"""Story workspace CRUD + the story-starter catalogue."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import prompts
from ..db import get_db
from ..deps import current_user_id, resolve_user
from ..metrics import agency_report
from ..models import (
    ConversationTurn, DraftSnapshot, ExperimentArm, StoryWorkspace, TelemetryEvent, User,
)
from ..schemas import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def current_user(db: Session, user_id: str | None = None) -> User:
    return resolve_user(db, user_id, "student")


# Autosave fires about once a second while the writer types; a version every
# couple of minutes is enough to get back to without flooding the list.
SNAPSHOT_EVERY = timedelta(minutes=2)
TITLE_MAX = 200


def snapshot(db: Session, ws: StoryWorkspace, reason: str, force: bool = False) -> None:
    """Record the workspace's current text as an earlier version.

    Autosave snapshots are throttled; `before_ask` and `before_restore` are
    always taken (`force`). Identical consecutive text is never stored twice.
    """
    last = db.scalar(
        select(DraftSnapshot)
        .where(DraftSnapshot.workspace_id == ws.workspace_id)
        .order_by(DraftSnapshot.created_at.desc())
    )
    if last and last.content == ws.current_content:
        return
    if not force and last is not None:
        created = last.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created < SNAPSHOT_EVERY:
            return
    db.add(DraftSnapshot(
        workspace_id=ws.workspace_id, content=ws.current_content, title=ws.title,
        words=len(ws.current_content.split()), reason=reason,
    ))


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
        goals=ws.goals or "",
        notes=ws.notes or "",
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
        chat_default_open=_chat_default_open(ws, owner, db),
    )


def _chat_default_open(ws: StoryWorkspace, owner: User | None, db: Session) -> bool:
    arm_id = ws.arm_id or (owner.arm_id if owner else "")
    arm = db.get(ExperimentArm, arm_id) if arm_id else None
    if arm is None:
        arm = db.scalar(select(ExperimentArm).where(ExperimentArm.is_default.is_(True)))
    return True if arm is None or arm.chat_default_open is None else arm.chat_default_open


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
        goals=body.goals,
        notes=body.notes,
        mode=body.mode,
        scaffold_intensity=body.scaffold_intensity,
        arm_id=user.arm_id,
    )
    db.add(ws)
    db.flush()
    snapshot(db, ws, "autosave", force=True)
    db.add(TelemetryEvent(
        workspace_id=ws.workspace_id, user_id=user.user_id, event_type="session_start",
        payload={"mode": body.mode, "seeded": bool(body.initial_prompt),
                 "has_notes": bool(body.notes.strip()),
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
    changes = body.model_dump(exclude_none=True)
    if "title" in changes:
        title = changes["title"].strip()
        if not title:
            # An empty title leaves a blank row in the student's story list.
            raise HTTPException(422, "A story needs a title.")
        changes["title"] = title[:TITLE_MAX]
    if "current_content" in changes and changes["current_content"] != ws.current_content:
        # Keep the text as it was *before* this change - that is the version a
        # writer wants back. (Snapshotting after the change only ever stored
        # what was already on screen.)
        snapshot(db, ws, "autosave")
    for field, value in changes.items():
        setattr(ws, field, value)
    db.commit()
    db.refresh(ws)
    return _serialize(ws, db)


@router.get("/{workspace_id}/versions")
def list_versions(workspace_id: str, db: Session = Depends(get_db)):
    """Earlier versions of the story, newest first."""
    if not db.get(StoryWorkspace, workspace_id):
        raise HTTPException(404, "Workspace not found")
    rows = db.scalars(
        select(DraftSnapshot)
        .where(DraftSnapshot.workspace_id == workspace_id)
        .order_by(DraftSnapshot.created_at.desc())
        .limit(100)
    )
    return [
        {"snapshot_id": r.snapshot_id, "content": r.content, "words": r.words,
         "reason": r.reason, "created_at": r.created_at.isoformat()}
        for r in rows
    ]


@router.post("/{workspace_id}/versions/{snapshot_id}/restore", response_model=WorkspaceOut)
def restore_version(
    workspace_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
    user_id: str | None = Depends(current_user_id),
):
    """Bring an earlier version back. The current text is saved first, so the
    restore can itself be undone from the same list."""
    ws = db.get(StoryWorkspace, workspace_id)
    snap = db.get(DraftSnapshot, snapshot_id)
    if not ws or not snap or snap.workspace_id != workspace_id:
        raise HTTPException(404, "Version not found")
    snapshot(db, ws, "before_restore", force=True)
    before = len(ws.current_content.split())
    ws.current_content = snap.content
    db.add(TelemetryEvent(
        workspace_id=workspace_id, user_id=user_id or ws.user_id,
        event_type="version_restored",
        payload={"snapshot_id": snapshot_id, "snapshot_reason": snap.reason,
                 "words_before": before, "words_after": snap.words},
    ))
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
            "declared_activity": t.declared_activity,
            "decided_activity": t.decided_activity or "",
            "selection": t.selection or "",
            "intercepted": t.intercepted,
            "node_path": t.node_path, "suggestions": t.suggestions,
            "provider": t.provider, "model_name": t.model_name,
            "scaffold_intensity": t.scaffold_intensity,
            "latency_ms": t.latency_ms, "timestamp": t.timestamp.isoformat(),
            "delivery": (t.fidelity or {}).get("delivery", "delivered"),
        }
        for t in rows
    ]
