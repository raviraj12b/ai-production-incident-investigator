"""Versioned HTTP contracts for incident intake."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    service: str = Field(min_length=1, max_length=120)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    window_start: datetime
    window_end: datetime

    @field_validator("window_start", "window_end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Incident times must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def valid_window(self):
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be later than window_start")
        return self


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str
    service: str
    severity: str
    status: str
    window_start: datetime
    window_end: datetime
    created_at: datetime
    updated_at: datetime
