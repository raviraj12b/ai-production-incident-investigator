"""Minimal reviewer authentication for the local MVP review boundary."""

import os
import re
import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


_bearer = HTTPBearer(auto_error=False)
_REVIEWER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+\-]{0,119}\Z")


@dataclass(frozen=True)
class ReviewerIdentity:
    reviewer_id: str


def authenticated_reviewer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ReviewerIdentity:
    """Authenticate one configured reviewer without trusting request identity fields."""
    reviewer_id = os.getenv("REVIEWER_ID", "").strip()
    expected_key = os.getenv("REVIEWER_API_KEY", "")
    if _REVIEWER_ID.fullmatch(reviewer_id) is None or len(expected_key) < 32:
        raise HTTPException(status_code=503, detail="Reviewer authentication is not configured")
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected_key)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid reviewer credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ReviewerIdentity(reviewer_id=reviewer_id)
