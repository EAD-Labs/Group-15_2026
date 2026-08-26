"""Request-scoped identity.

Prototype-grade only. The portals send an X-User-Id header that the browser
stores locally; there is no password, no token, and no server-side session.
HLD 7.2 specifies JWT/OAuth2 for the real system - the User entity and role
field here are shaped so that swap is additive rather than structural.
"""
from fastapi import Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User


def _next_participant_code(db: Session) -> str:
    n = len(list(db.scalars(select(User).where(User.role == "student")))) + 1
    return f"Participant_{n:02d}"


def resolve_user(db: Session, user_id: str | None, role: str = "student") -> User:
    if user_id:
        user = db.get(User, user_id)
        if user:
            return user
    # No identity yet: fall back to the first user holding this role, or make one.
    user = db.scalar(select(User).where(User.role == role).order_by(User.created_at))
    if user:
        return user
    user = User(
        display_name="Researcher" if role == "researcher" else "Student",
        role=role,
        participant_code="" if role == "researcher" else _next_participant_code(db),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_named(db: Session, display_name: str, role: str) -> User:
    """Sign-in by name. Reuses the row if this person has been here before."""
    name = (display_name or "").strip() or ("Researcher" if role == "researcher" else "Student")
    user = db.scalar(
        select(User).where(User.display_name == name, User.role == role)
    )
    if user:
        return user
    user = User(
        display_name=name,
        role=role,
        participant_code="" if role == "researcher" else _next_participant_code(db),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def current_user_id(x_user_id: str | None = Header(default=None)) -> str | None:
    return x_user_id
