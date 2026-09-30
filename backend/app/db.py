"""SQLAlchemy session factory.

SQLite for the local MVP; the URL is the only thing that changes for the
PostgreSQL deployment described in HLD 8.3.
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after a table first existed. `create_all` creates missing
# tables but never alters existing ones, so a database from an earlier
# iteration would otherwise fail on the first query touching a new column.
# Additive only - nothing here drops, renames or rewrites data.
_ADDED_COLUMNS = [
    ("experiment_arms", "role_id", "VARCHAR DEFAULT ''"),
    ("story_workspaces", "goals", "TEXT DEFAULT ''"),
    ("story_workspaces", "notes", "TEXT DEFAULT ''"),
    ("conversation_turns", "declared_activity", "VARCHAR DEFAULT ''"),
    ("conversation_turns", "role_version_id", "VARCHAR DEFAULT ''"),
    ("conversation_turns", "decided_activity", "VARCHAR DEFAULT ''"),
    ("conversation_turns", "activity_evidence", "JSON"),
    ("conversation_turns", "draft_words", "INTEGER DEFAULT 0"),
    ("conversation_turns", "selection", "TEXT DEFAULT ''"),
]


def ensure_columns() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            if not insp.has_table(table):
                continue
            if column in {c["name"] for c in insp.get_columns(table)}:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
