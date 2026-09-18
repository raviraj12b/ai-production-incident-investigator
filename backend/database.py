"""Lazy connection setup; schema changes belong to Alembic, never startup."""

from functools import lru_cache
from typing import Iterator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is required for product API")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must use postgresql+psycopg://")
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    try:
        factory = session_factory()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    with factory() as session:
        yield session
