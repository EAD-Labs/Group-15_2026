"""Experiment design and outcome comparison.

The point of this module is to make "we changed X and students did Y" a query
rather than an anecdote. Conditions are named and stored; every workspace and
turn records the condition it was produced under; outcomes are aggregated per
condition on the same measures.
"""
import random
import statistics
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..metrics import agency_report
from ..models import (
    AIRole, ArmVersion, ConversationTurn, ExperimentArm, StoryWorkspace, TelemetryEvent, User,
)
from ..prompts import (
    BASE_SYSTEM_PROMPT, BASE_SYSTEM_PROMPT_V2, CONTROL_SYSTEM_PROMPT, RESPONSE_CONTRACT_V2,
    SCAFFOLD_INTENSITY, TUTOR_PLANNING_FRAGMENT, TUTOR_PLANNING_FRAGMENT_V2,
    TUTOR_REVIEWING_FRAGMENT, TUTOR_REVIEWING_FRAGMENT_V2, TUTOR_TRANSLATING_FRAGMENT,
    TUTOR_TRANSLATING_FRAGMENT_V2,
)
from ..schemas import ArmIn, ArmOut, AssignIn

router = APIRouter(prefix="/api/research/experiments", tags=["experiments"])

_ACTIVITIES = ("planning", "translation", "reviewing", "other")


def _out(a: ExperimentArm, n_participants: int = 0, role: AIRole | None = None) -> ArmOut:
    return ArmOut(
        arm_id=a.arm_id, name=a.name, description=a.description,
        provider=a.provider, model_name=a.model_name, temperature=a.temperature,
        guardrail_strictness=a.guardrail_strictness,
        role_id=a.role_id,
        scaffold_intensity=a.scaffold_intensity, system_prompt=a.system_prompt,
        allow_student_intensity=a.allow_student_intensity,
        allow_student_model=a.allow_student_model,
        allowed_providers=a.allowed_providers or [],
        chat_default_open=a.chat_default_open if a.chat_default_open is not None else True,
        on_provider_failure=a.on_provider_failure or "fail",
        version=a.version or 1,
        is_control=a.is_control, is_default=a.is_default, active=a.active,
        participants=n_participants,
        role_name=role.name if role else None,
    )


# Everything about a condition that can change what a participant experiences.
# Snapshotted whole into ArmVersion on creation and on every edit that touches
# one of them. Labels and bookkeeping (name, description, is_default,
# is_control, active) change nothing a participant sees, so they don't version.
_VERSIONED_FIELDS = (
    "provider", "model_name", "temperature",
    "guardrail_strictness", "role_id", "scaffold_intensity", "system_prompt",
    "allow_student_intensity", "allow_student_model", "allowed_providers",
    "chat_default_open", "on_provider_failure",
)


def _settings(arm: ExperimentArm) -> dict:
    return {f: getattr(arm, f) for f in _VERSIONED_FIELDS}


def record_arm_version(db: Session, arm: ExperimentArm) -> None:
    """Append the arm's current settings as version `arm.version`."""
    db.add(ArmVersion(arm_id=arm.arm_id, version=arm.version or 1, settings=_settings(arm)))


def backfill_arm_versions(db: Session) -> None:
    """Give every arm from before versioning its version-1 snapshot."""
    have = {v.arm_id for v in db.scalars(select(ArmVersion))}
    missing = [a for a in db.scalars(select(ExperimentArm)) if a.arm_id not in have]
    for arm in missing:
        arm.version = arm.version or 1
        record_arm_version(db, arm)
    if missing:
        db.commit()


def _counts(db: Session) -> dict[str, int]:
    c: Counter = Counter()
    for u in db.scalars(select(User).where(User.role == "student")):
        if u.arm_id:
            c[u.arm_id] += 1
    return dict(c)


def ensure_default_roles(db: Session) -> dict[str, AIRole]:
    """Seed the two default roles on first boot, mirroring today's arms exactly.

    Returns a dict keyed by archetype name for easy lookup.
    Socratic Tutor: guardrail_strictness == 2 equivalent.
    Ghost baseline: guardrail_strictness == 0 equivalent.
    """
    # Order by version so that, once a role has been edited, the archetype key
    # resolves to its latest version rather than an arbitrary one.
    existing = {
        r.archetype: r
        for r in db.scalars(select(AIRole).order_by(AIRole.version))
    }
    roles = {}

    if "tutor" not in existing:
        tutor = AIRole(name="Socratic Tutor", version=1, **_TUTOR_V2)
        db.add(tutor)
        roles["tutor"] = tutor
    else:
        tutor = existing["tutor"]
        # One-time reconciliation: a Phase 1 seed tutor (v1, stock base prompt,
        # no activity fragments) predates Phase 2. Fill the fragments so
        # activity-conditioned behaviour works out of the box. A researcher edit
        # bumps the version, so this can never overwrite one.
        if (tutor.version == 1
                and tutor.base_prompt == BASE_SYSTEM_PROMPT
                and not (tutor.planning_prompt or tutor.translating_prompt
                         or tutor.reviewing_prompt)):
            tutor.planning_prompt = TUTOR_PLANNING_FRAGMENT
            tutor.translating_prompt = TUTOR_TRANSLATING_FRAGMENT
            tutor.reviewing_prompt = TUTOR_REVIEWING_FRAGMENT
        roles["tutor"] = _upgrade_stock_tutor(db, tutor)

    if "ghost" not in existing:
        ghost = AIRole(
            name="Ghost baseline",
            archetype="ghost",
            behaviour="direct_generation",
            base_prompt=CONTROL_SYSTEM_PROMPT,
            planning_prompt="",
            translating_prompt="",
            reviewing_prompt="",
            may_produce_prose=True,
            enforcement_level=0,
        )
        db.add(ghost)
        roles["ghost"] = ghost
    else:
        roles["ghost"] = existing["ghost"]

    db.commit()
    # Refresh to get role_ids populated
    for r in roles.values():
        db.refresh(r)
    return roles


# The Socratic Tutor under response contract v2 (Florence's heuristic
# evaluation, H4-H7). Seeded as-is on a fresh database.
_TUTOR_V2 = dict(
    archetype="tutor",
    behaviour="socratic_questioning",
    base_prompt=BASE_SYSTEM_PROMPT_V2,
    planning_prompt=TUTOR_PLANNING_FRAGMENT_V2,
    translating_prompt=TUTOR_TRANSLATING_FRAGMENT_V2,
    reviewing_prompt=TUTOR_REVIEWING_FRAGMENT_V2,
    may_produce_prose=False,
    enforcement_level=2,
    response_contract=RESPONSE_CONTRACT_V2,
)


def _upgrade_stock_tutor(db: Session, tutor: AIRole) -> AIRole:
    """Move an untouched stock v1 Tutor to contract v2 - append-only.

    Writes v2 as a *new version* of the role (parent = the v1 row) and
    repoints the conditions that used v1, bumping their versions, exactly as a
    researcher's edit would. Turns already produced under v1 keep pointing at
    v1. A Tutor a researcher has edited is never touched: their edit is a
    deliberate configuration, and replacing it would be our edit, not theirs.
    """
    stock_v1 = (
        (tutor.response_contract or "v1") == "v1"
        and tutor.base_prompt == BASE_SYSTEM_PROMPT
        and tutor.planning_prompt == TUTOR_PLANNING_FRAGMENT
        and tutor.translating_prompt == TUTOR_TRANSLATING_FRAGMENT
        and tutor.reviewing_prompt == TUTOR_REVIEWING_FRAGMENT
        and tutor.enforcement_level == 2
        and not tutor.may_produce_prose
    )
    if not stock_v1:
        return tutor
    upgraded = AIRole(
        name=tutor.name, version=tutor.version + 1, parent_role_id=tutor.role_id, **_TUTOR_V2,
    )
    db.add(upgraded)
    db.flush()
    arms = list(db.scalars(select(ExperimentArm).where(ExperimentArm.role_id == tutor.role_id)))
    if arms:
        backfill_arm_versions(db)
    for arm in arms:
        arm.role_id = upgraded.role_id
        arm.version = (arm.version or 1) + 1
        record_arm_version(db, arm)
    db.add(TelemetryEvent(
        event_type="role_updated",
        payload={"from_role_id": tutor.role_id, "to_role_id": upgraded.role_id,
                 "version": upgraded.version, "changes": ["response_contract v1 -> v2"],
                 "arms_repointed": len(arms), "automatic": True},
    ))
    return upgraded


def backfill_arm_roles(db: Session) -> None:
    """Attach a role to any arm created before the role seam existed.

    Uses the same mapping the pre-role system implied: guardrail_strictness == 0
    is a Ghost, everything else is a Socratic Tutor. Idempotent and cheap, so
    it is safe to call from any read path.
    """
    missing = list(db.scalars(
        select(ExperimentArm).where(
            (ExperimentArm.role_id == "") | (ExperimentArm.role_id.is_(None))
        )
    ))
    if not missing:
        return
    roles = ensure_default_roles(db)
    for arm in missing:
        target = roles["ghost"] if arm.guardrail_strictness == 0 else roles["tutor"]
        arm.role_id = target.role_id
    db.commit()


def ensure_default_arms(db: Session) -> None:
    """Seed a two-arm study so the comparison view is never empty on arrival."""
    if db.scalar(select(ExperimentArm)):
        backfill_arm_roles(db)
        backfill_arm_versions(db)
        return
    roles = ensure_default_roles(db)

    # Seed with the *configured* provider, not the effective one. Seeding with
    # effective_provider meant a first boot without a key saved both
    # conditions as the offline scaffold for good - adding GEMINI_API_KEY
    # later then changed nothing. With no key, a Gemini turn already falls
    # back to the offline scaffold per turn, so nothing breaks either way.
    db.add_all([
        ExperimentArm(
            name="Socratic guardrail", is_control=False, is_default=True,
            description="The intervention: executive requests are intercepted and "
                        "converted into questions.",
            provider=settings.default_provider, guardrail_strictness=2,
            role_id=roles["tutor"].role_id,
            scaffold_intensity="balanced", allow_student_intensity=True,
            allow_student_model=True, allowed_providers=["gemini", "ollama", "echo"],
        ),
        ExperimentArm(
            name="Unguarded assistant", is_control=True,
            description="Control: an ordinary AI writing assistant that complies "
                        "with requests to write.",
            provider=settings.default_provider, guardrail_strictness=0,
            role_id=roles["ghost"].role_id,
            scaffold_intensity="balanced", allow_student_intensity=True,
            allow_student_model=True, allowed_providers=["gemini", "ollama", "echo"],
        ),
    ])
    db.commit()
    backfill_arm_versions(db)


def _role_map(db: Session) -> dict[str, AIRole]:
    return {r.role_id: r for r in db.scalars(select(AIRole))}


@router.get("", response_model=list[ArmOut])
def list_arms(db: Session = Depends(get_db)):
    ensure_default_arms(db)
    counts = _counts(db)
    roles = _role_map(db)
    rows = db.scalars(select(ExperimentArm).order_by(ExperimentArm.created_at))
    return [_out(a, counts.get(a.arm_id, 0), roles.get(a.role_id)) for a in rows]


@router.post("", response_model=ArmOut)
def create_arm(body: ArmIn, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_none=True)
    if not data.get("role_id"):
        # A condition without a role is not a valid experiment. Default to the
        # Socratic Tutor, matching where an unassigned participant lands.
        data["role_id"] = ensure_default_roles(db)["tutor"].role_id
    arm = ExperimentArm(**data, version=1)
    db.add(arm)
    db.flush()
    record_arm_version(db, arm)
    db.add(TelemetryEvent(event_type="arm_created", payload={"name": arm.name}))
    db.commit()
    db.refresh(arm)
    return _out(arm, 0, db.get(AIRole, arm.role_id) if arm.role_id else None)


@router.patch("/{arm_id}", response_model=ArmOut)
def update_arm(arm_id: str, body: ArmIn, db: Session = Depends(get_db)):
    arm = db.get(ExperimentArm, arm_id)
    if not arm:
        raise HTTPException(404, "Condition not found")
    changes = body.model_dump(exclude_none=True)
    # Append-only (defect D1): the arm keeps its id, but each edit becomes a
    # new version with its full settings stored in ArmVersion, and turns
    # record the version they ran under. The diff in telemetry is a
    # convenience; the ArmVersion rows are the record.
    diff = {
        k: {"from": getattr(arm, k, None), "to": v}
        for k, v in changes.items()
        if getattr(arm, k, None) != v
    }
    for flag in ("is_default", "is_control"):
        if changes.get(flag):
            for other in db.scalars(select(ExperimentArm).where(ExperimentArm.arm_id != arm_id)):
                setattr(other, flag, False)
    for k, v in changes.items():
        setattr(arm, k, v)
    if any(k in _VERSIONED_FIELDS for k in diff):
        backfill_arm_versions(db)  # make sure the pre-edit version is on record
        arm.version = (arm.version or 1) + 1
        record_arm_version(db, arm)
    db.add(TelemetryEvent(
        event_type="arm_updated",
        payload={"arm_id": arm_id, "version": arm.version, "changes": diff},
    ))
    db.commit()
    db.refresh(arm)
    role = db.get(AIRole, arm.role_id) if arm.role_id else None
    return _out(arm, _counts(db).get(arm_id, 0), role)


@router.get("/{arm_id}/versions")
def arm_versions(arm_id: str, db: Session = Depends(get_db)):
    """Every version of a condition's settings, oldest first."""
    rows = db.scalars(
        select(ArmVersion).where(ArmVersion.arm_id == arm_id).order_by(ArmVersion.version)
    )
    return [{"version": v.version, "settings": v.settings,
             "created_at": v.created_at.isoformat()} for v in rows]


@router.delete("/{arm_id}")
def delete_arm(arm_id: str, db: Session = Depends(get_db)):
    arm = db.get(ExperimentArm, arm_id)
    if not arm:
        raise HTTPException(404, "Condition not found")
    # Unassign rather than orphan; historical turns keep their arm_id so past
    # results stay interpretable.
    for u in db.scalars(select(User).where(User.arm_id == arm_id)):
        u.arm_id = ""
    db.delete(arm)
    db.commit()
    return {"ok": True}


@router.post("/assign")
def assign(body: AssignIn, db: Session = Depends(get_db)):
    """Assign participants to conditions, by hand or at random."""
    students = list(db.scalars(select(User).where(User.role == "student")))
    arms = [a for a in db.scalars(select(ExperimentArm).where(ExperimentArm.active.is_(True)))]
    if not arms:
        raise HTTPException(400, "No active conditions to assign to")

    if body.randomise:
        pool = students if body.include_assigned else [u for u in students if not u.arm_id]
        rng = random.Random(body.seed) if body.seed is not None else random.Random()
        rng.shuffle(pool)
        # Round-robin over a shuffled pool: balanced group sizes, random membership.
        for i, u in enumerate(pool):
            u.arm_id = arms[i % len(arms)].arm_id
        changed = len(pool)
    else:
        if not body.user_id or not body.arm_id:
            raise HTTPException(400, "user_id and arm_id are required unless randomising")
        user = db.get(User, body.user_id)
        if not user:
            raise HTTPException(404, "Participant not found")
        user.arm_id = body.arm_id
        changed = 1

    db.add(TelemetryEvent(
        event_type="assignment",
        payload={"randomised": body.randomise, "changed": changed},
    ))
    db.commit()
    return {"ok": True, "assigned": changed}


@router.get("/compare")
def compare(db: Session = Depends(get_db)):
    """Outcome measures per condition, on identical definitions.

    Answers the question the client actually has: if we change the guardrail,
    the model, or the scaffold intensity, what do students do differently?
    """
    ensure_default_arms(db)
    arms = list(db.scalars(select(ExperimentArm).order_by(ExperimentArm.created_at)))
    workspaces = list(db.scalars(select(StoryWorkspace)))
    turns = list(db.scalars(select(ConversationTurn)))
    users = {u.user_id: u for u in db.scalars(select(User))}

    user_turns = [t for t in turns if t.speaker == "user"]
    ai_turns = [t for t in turns if t.speaker == "ai"]

    def arm_of(ws: StoryWorkspace) -> str:
        if ws.arm_id:
            return ws.arm_id
        u = users.get(ws.user_id)
        return u.arm_id if u else ""

    rows = []
    for arm in arms:
        ws_in_arm = [w for w in workspaces if arm_of(w) == arm.arm_id]
        ids = {w.workspace_id for w in ws_in_arm}
        u_turns = [t for t in user_turns if t.workspace_id in ids]
        a_turns = [t for t in ai_turns if t.workspace_id in ids]

        agencies, retentions, words = [], [], []
        act_ret: dict[str, list[float]] = {a: [] for a in _ACTIVITIES}
        for w in ws_in_arm:
            ws_ai = [t for t in a_turns if t.workspace_id == w.workspace_id]
            rep = agency_report(w.current_content, [t.message_text for t in ws_ai])
            if rep["total_words"]:
                agencies.append(rep["agency_ratio"])
                retentions.append(rep["ai_retention_rouge_l"])
                words.append(rep["total_words"])
                # Retention split by the AI turn's writing activity (defect D4 /
                # Q5): lets the arms x activities x retention comparison be read
                # off directly, which the C&C '24 paper could not do.
                for act in _ACTIVITIES:
                    act_texts = [t.message_text for t in ws_ai if t.cognitive_activity == act]
                    if act_texts:
                        act_ret[act].append(
                            agency_report(w.current_content, act_texts)["ai_retention_rouge_l"]
                        )

        intercepts = sum(1 for t in u_turns if t.intercepted)
        latencies = [t.latency_ms for t in a_turns if t.latency_ms]
        participants = sum(1 for u in users.values()
                           if u.role == "student" and u.arm_id == arm.arm_id)

        rows.append({
            "arm_id": arm.arm_id,
            "name": arm.name,
            "is_control": arm.is_control,
            "config": {
                "provider": arm.provider,
                "model_name": arm.model_name,
                "temperature": arm.temperature,
                "guardrail_strictness": arm.guardrail_strictness,
                "scaffold_intensity": arm.scaffold_intensity,
            },
            "participants": participants,
            "workspaces": len(ws_in_arm),
            "exchanges": len(u_turns),
            # --- outcome measures, identical definitions across arms --------
            "mean_agency": round(statistics.fmean(agencies), 3) if agencies else None,
            "mean_ai_retention": round(statistics.fmean(retentions), 3) if retentions else None,
            "retention_by_activity": {
                act: round(statistics.fmean(v), 3) if v else None
                for act, v in act_ret.items()
            },
            "mean_words": round(statistics.fmean(words), 1) if words else None,
            "words_per_exchange": (
                round(sum(words) / len(u_turns), 1) if words and u_turns else None
            ),
            "intercept_rate": round(intercepts / len(u_turns), 3) if u_turns else None,
            "median_latency_ms": int(statistics.median(latencies)) if latencies else None,
            "intent_distribution": dict(
                Counter(t.intent_type for t in u_turns if t.intent_type)
            ),
            "cognitive_distribution": dict(
                Counter(t.cognitive_activity for t in u_turns if t.cognitive_activity)
            ),
            "decided_distribution": dict(
                Counter(t.decided_activity for t in u_turns if t.decided_activity)
            ),
            "intensity_used": dict(
                Counter(t.scaffold_intensity for t in a_turns if t.scaffold_intensity)
            ),
        })

    unassigned = sum(1 for u in users.values() if u.role == "student" and not u.arm_id)
    return {
        "arms": rows,
        "unassigned_participants": unassigned,
        "measures": {
            "mean_agency": "1 − (draft 5-grams also found in AI output) ÷ draft 5-grams. Higher = more of the text is the student's own language.",
            "mean_ai_retention": "ROUGE-L recall of AI output within the draft (Chakrabarty et al., C&C '24, Fig. 7). Higher = more of what the AI said ended up in the story.",
            "words_per_exchange": "Draft words divided by student instructions. A productivity-per-interaction measure.",
            "intercept_rate": "Share of student instructions the Helsinki filter intercepted.",
        },
        "intensities": [
            {"id": k, "label": v["label"], "blurb": v["blurb"]}
            for k, v in SCAFFOLD_INTENSITY.items()
        ],
    }


def default_arm(db: Session) -> ExperimentArm | None:
    """Where a participant with no assignment lands."""
    ensure_default_arms(db)
    backfill_arm_roles(db)
    return (
        db.scalar(select(ExperimentArm).where(ExperimentArm.is_default.is_(True)))
        or db.scalar(select(ExperimentArm).order_by(ExperimentArm.created_at))
    )
