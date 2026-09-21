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


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focus: str | None = Field(default=None, min_length=1, max_length=500)


class JobOut(BaseModel):
    status: str
    attempts: int


class InvestigationOut(BaseModel):
    id: str
    incident_id: str
    parent_id: str | None
    status: str
    focus: str | None
    window_start: datetime
    window_end: datetime
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    job: JobOut


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    investigation_id: str
    kind: Literal["LOG", "TRACE", "METRIC", "CHANGE"]
    observed_at: datetime
    service: str
    summary: str
    source_backend: str
    source_ref: str
    trace_id: str | None
    captured_at: datetime


class EvidenceLinkOut(BaseModel):
    evidence_id: str
    relation: Literal["SUPPORTS", "CONTRADICTS"]


class HypothesisOut(BaseModel):
    id: str
    explanation: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    missing_evidence: list[str]
    evidence: list[EvidenceLinkOut]


class ReportOut(BaseModel):
    id: str
    investigation_id: str
    summary: str
    uncertainty: str
    created_at: datetime
    hypotheses: list[HypothesisOut]
