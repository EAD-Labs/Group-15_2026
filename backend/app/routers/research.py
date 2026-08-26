"""Researcher surface: provider control, prompt config, telemetry, exports.

Covers UC-03 (swap the model without a restart), UC-04 (export class-wide
conversation histories) and UC-05 (edit prompts and interaction parameters).
"""
import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..metrics import agency_report
from ..models import ConversationTurn, PromptConfig, StoryWorkspace, TelemetryEvent, User
from ..prompts import BASE_SYSTEM_PROMPT
from ..providers import available_providers, get_provider
from ..schemas import ConfigIn, EventIn

router = APIRouter(prefix="/api/research", tags=["research"])


# --------------------------------------------------------------------------
# Providers (UC-03)
# --------------------------------------------------------------------------

@router.get("/providers")
async def providers():
    out = []
    for p in available_providers():
        ok, status = await get_provider(p["id"]).health()
        out.append({**p, "healthy": ok, "status": status})
    return {"providers": out, "default": settings.effective_provider}


# --------------------------------------------------------------------------
# Prompt configuration (UC-05)
# --------------------------------------------------------------------------

def _ensure_config(db: Session) -> PromptConfig:
    cfg = db.scalar(select(PromptConfig).where(PromptConfig.active_flag.is_(True)))
    if not cfg:
        cfg = PromptConfig(
            label="Default Socratic Scaffold",
            provider=settings.effective_provider,
            model_name=settings.gemini_model if settings.effective_provider == "gemini" else "offline-socratic-v1",
            system_prompt="",
            active_flag=True,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = _ensure_config(db)
    return {
        "config_id": cfg.config_id, "label": cfg.label, "provider": cfg.provider,
        "model_name": cfg.model_name, "system_prompt": cfg.system_prompt,
        "temperature": cfg.temperature, "max_tokens": cfg.max_tokens,
        "guardrail_strictness": cfg.guardrail_strictness,
        "default_system_prompt": BASE_SYSTEM_PROMPT,
    }


@router.patch("/config")
def update_config(body: ConfigIn, db: Session = Depends(get_db)):
    cfg = _ensure_config(db)
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(cfg, field, value)
    # Config changes are themselves research data - A/B arms must be reconstructable.
    db.add(TelemetryEvent(event_type="config_change", payload={"changes": changes}))
    db.commit()
    db.refresh(cfg)
    return {"ok": True, "changed": list(changes.keys()), "config_id": cfg.config_id}


# --------------------------------------------------------------------------
# Telemetry ingest + live feed
# --------------------------------------------------------------------------

@router.post("/events")
def record_event(body: EventIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.role == "student"))
    db.add(TelemetryEvent(
        workspace_id=body.workspace_id,
        user_id=user.user_id if user else "",
        event_type=body.event_type,
        delta_change=body.delta_change,
        duration_ms=body.duration_ms,
        payload=body.payload,
    ))
    db.commit()
    return {"ok": True}


@router.get("/events")
def list_events(limit: int = 100, workspace_id: str = "", db: Session = Depends(get_db)):
    q = select(TelemetryEvent).order_by(TelemetryEvent.timestamp.desc()).limit(limit)
    if workspace_id:
        q = q.where(TelemetryEvent.workspace_id == workspace_id)
    return [
        {
            "event_id": e.event_id, "workspace_id": e.workspace_id,
            "event_type": e.event_type, "delta_change": e.delta_change,
            "duration_ms": e.duration_ms, "payload": e.payload,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in db.scalars(q)
    ]


# --------------------------------------------------------------------------
# Aggregate study view
# --------------------------------------------------------------------------

@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    workspaces = list(db.scalars(select(StoryWorkspace)))
    turns = list(db.scalars(select(ConversationTurn)))
    events = list(db.scalars(select(TelemetryEvent)))

    ai_turns = [t for t in turns if t.speaker == "ai"]
    user_turns = [t for t in turns if t.speaker == "user"]
    intents = Counter(t.intent_type for t in user_turns if t.intent_type)
    cognitive = Counter(t.cognitive_activity for t in user_turns if t.cognitive_activity)
    intercepts = sum(1 for t in user_turns if t.intercepted)
    latencies = sorted(t.latency_ms for t in ai_turns if t.latency_ms)

    per_ws = []
    total_words = 0
    agency_values = []
    retention_values = []
    for ws in workspaces:
        ai_texts = [t.message_text for t in ai_turns if t.workspace_id == ws.workspace_id]
        rep = agency_report(ws.current_content, ai_texts)
        total_words += rep["total_words"]
        if rep["total_words"] > 0:
            agency_values.append(rep["agency_ratio"])
            retention_values.append(rep["ai_retention_rouge_l"])
        per_ws.append({
            "workspace_id": ws.workspace_id, "title": ws.title, "mode": ws.mode,
            "words": rep["total_words"], "agency_ratio": rep["agency_ratio"],
            "ai_retention": rep["ai_retention_rouge_l"],
            "borrowed_ngrams": rep["borrowed_ngrams"],
            "turns": sum(1 for t in user_turns if t.workspace_id == ws.workspace_id),
            "updated_at": ws.updated_at.isoformat(),
        })

    enforcement = Counter()
    for e in events:
        if e.event_type == "ai_response":
            for tag in e.payload.get("enforcement", []):
                enforcement[tag] += 1

    return {
        "workspaces": len(workspaces),
        "total_words": total_words,
        "exchanges": len(user_turns),
        "intercepts": intercepts,
        "intercept_rate": round(intercepts / len(user_turns), 3) if user_turns else 0.0,
        "mean_agency": round(sum(agency_values) / len(agency_values), 3) if agency_values else 1.0,
        "median_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
        "intent_distribution": dict(intents),
        "cognitive_distribution": dict(cognitive),
        "mean_ai_retention": (
            round(sum(retention_values) / len(retention_values), 3)
            if retention_values else 0.0
        ),
        "enforcement_actions": dict(enforcement),
        "event_count": len(events),
        "per_workspace": per_ws,
    }


@router.get("/timeline")
def timeline(workspace_id: str = "", limit: int = 200, db: Session = Depends(get_db)):
    """Instruction sequence, in order, on both classification axes.

    This is the data behind Figure 6 of Chakrabarty et al. (C&C '24), which
    plots instruction type against instruction index to show that writers move
    between planning, translating and reviewing non-linearly rather than in
    phases. Reproducing it per session lets the client test whether the same
    non-linearity holds for students under a Socratic guardrail.
    """
    q = (
        select(ConversationTurn)
        .where(ConversationTurn.speaker == "user")
        .order_by(ConversationTurn.timestamp)
        .limit(limit)
    )
    if workspace_id:
        q = q.where(ConversationTurn.workspace_id == workspace_id)
    return {
        "points": [
            {
                "index": i,
                "workspace_id": t.workspace_id,
                "intent": t.intent_type,
                "cognitive": t.cognitive_activity,
                "intercepted": t.intercepted,
                "message": t.message_text[:120],
                "timestamp": t.timestamp.isoformat(),
            }
            for i, t in enumerate(db.scalars(q), 1)
        ]
    }


# --------------------------------------------------------------------------
# Export (UC-02 student, UC-04 researcher)
# --------------------------------------------------------------------------

def _anonymise(db: Session) -> dict[str, str]:
    """Map real ids to Participant_NN, per HLD 11.4 telemetry anonymisation."""
    users = list(db.scalars(select(User).order_by(User.created_at)))
    return {u.user_id: f"Participant_{i:02d}" for i, u in enumerate(users, 1)}


@router.get("/export.json")
def export_json(workspace_id: str = "", db: Session = Depends(get_db)):
    codes = _anonymise(db)
    ws_q = select(StoryWorkspace)
    if workspace_id:
        ws_q = ws_q.where(StoryWorkspace.workspace_id == workspace_id)
    workspaces = list(db.scalars(ws_q))
    ids = {w.workspace_id for w in workspaces}

    turns = [t for t in db.scalars(select(ConversationTurn).order_by(ConversationTurn.timestamp))
             if t.workspace_id in ids]
    events = [e for e in db.scalars(select(TelemetryEvent).order_by(TelemetryEvent.timestamp))
              if not workspace_id or e.workspace_id in ids]

    payload = {
        "export_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "study": "Human-AI Co-Creative Storytelling (ET617 Group 15)",
            "anonymised": True,
            "schema_version": "1.0",
        },
        "workspaces": [
            {
                "workspace_id": w.workspace_id,
                "participant": codes.get(w.user_id, "Participant_XX"),
                "title": w.title, "mode": w.mode, "initial_prompt": w.initial_prompt,
                "final_text": w.current_content,
                "agency": agency_report(
                    w.current_content,
                    [t.message_text for t in turns
                     if t.workspace_id == w.workspace_id and t.speaker == "ai"],
                ),
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat(),
            }
            for w in workspaces
        ],
        "conversation_turns": [
            {
                "turn_id": t.turn_id, "workspace_id": t.workspace_id, "speaker": t.speaker,
                "message_text": t.message_text, "intent_type": t.intent_type,
                "cognitive_activity": t.cognitive_activity,
                "intercepted": t.intercepted, "node_path": t.node_path,
                "suggestions": t.suggestions, "provider": t.provider,
                "model_name": t.model_name, "latency_ms": t.latency_ms,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in turns
        ],
        "telemetry_events": [
            {
                "event_id": e.event_id, "workspace_id": e.workspace_id,
                "participant": codes.get(e.user_id, "Participant_XX"),
                "event_type": e.event_type, "delta_change": e.delta_change,
                "duration_ms": e.duration_ms, "payload": e.payload,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="storystudio-export-{stamp}.json"'},
    )


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    codes = _anonymise(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "timestamp", "participant", "workspace_id", "event_type",
        "intent", "cognitive_activity", "intercepted",
        "delta_change", "duration_ms", "detail",
    ])
    for e in db.scalars(select(TelemetryEvent).order_by(TelemetryEvent.timestamp)):
        p = e.payload or {}
        detail = p.get("message") or p.get("model") or p.get("original_request") or ""
        w.writerow([
            e.timestamp.isoformat(), codes.get(e.user_id, "Participant_XX"),
            e.workspace_id, e.event_type, p.get("intent", ""),
            p.get("cognitive", ""), p.get("intercepted", ""),
            e.delta_change, e.duration_ms,
            str(detail)[:200],
        ])
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="storystudio-telemetry-{stamp}.csv"'},
    )
