"""Portal entry. Implements the Login / Auth screen in HLD 9.1."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user_id, get_or_create_named
from ..models import User
from ..models import ExperimentArm
from ..prompts import SCAFFOLD_INTENSITY, TEMPLATES
from ..providers import available_providers, get_provider
from ..schemas import SessionIn, UserOut

router = APIRouter(prefix="/api", tags=["session"])


def _out(u: User) -> UserOut:
    return UserOut(
        user_id=u.user_id, display_name=u.display_name, role=u.role,
        participant_code=u.participant_code, arm_id=u.arm_id,
    )


@router.post("/session", response_model=UserOut)
def sign_in(body: SessionIn, db: Session = Depends(get_db)):
    role = body.role if body.role in {"student", "researcher"} else "student"
    return _out(get_or_create_named(db, body.display_name, role))


@router.get("/session", response_model=UserOut | None)
def whoami(
    db: Session = Depends(get_db),
    user_id: str | None = Depends(current_user_id),
):
    if not user_id:
        return None
    user = db.get(User, user_id)
    return _out(user) if user else None


@router.get("/participants", response_model=list[UserOut])
def participants(db: Session = Depends(get_db)):
    """Everyone who has written in this instance - the researcher's cohort."""
    rows = db.scalars(
        select(User).where(User.role == "student").order_by(User.created_at)
    )
    return [_out(u) for u in rows]


@router.get("/options")
async def student_options(
    db: Session = Depends(get_db),
    user_id: str | None = Depends(current_user_id),
):
    """What this student may change, given the condition they are assigned to.

    The researcher decides which knobs are exposed; the student sees only
    those. An unassigned student gets the permissive default.
    """
    from .experiments import default_arm
    user = db.get(User, user_id) if user_id else None
    arm = db.get(ExperimentArm, user.arm_id) if user and user.arm_id else None
    if arm is None:
        arm = default_arm(db)

    allow_intensity = arm.allow_student_intensity if arm else True
    allow_model = arm.allow_student_model if arm else True
    allowed = set(arm.allowed_providers or []) if arm else None

    providers = []
    if allow_model:
        for p in available_providers():
            if allowed is not None and p["id"] not in allowed:
                continue
            ok, status = await get_provider(p["id"]).health()
            providers.append({**p, "healthy": ok, "status": status})

    return {
        "condition": {"arm_id": arm.arm_id, "name": arm.name} if arm else None,
        "guardrail_active": (arm.guardrail_strictness if arm else 2) > 0,
        "allow_intensity": allow_intensity,
        "allow_model": allow_model,
        "intensities": [
            {"id": k, "label": v["label"], "blurb": v["blurb"]}
            for k, v in SCAFFOLD_INTENSITY.items()
        ],
        "providers": providers,
    }


@router.get("/templates")
def templates():
    return {"templates": TEMPLATES}
