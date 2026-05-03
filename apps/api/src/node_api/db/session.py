"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from node_api.config import settings
from node_api.repo_root import api_project_root


def _default_sqlite_url() -> str:
    path = (api_project_root() / "node.sqlite").resolve()
    return f"sqlite:///{path.as_posix()}"


def _make_engine() -> Engine:
    url = settings.database_url or _default_sqlite_url()
    sqlite = url.startswith("sqlite")
    kwargs: dict[str, object] = {}
    if sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine: Engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
