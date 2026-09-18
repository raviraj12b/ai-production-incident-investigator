"""Product state. Simulator modes and ground truth are deliberately excluded."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    service: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="ck_incident_window"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_incident_status"),
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_incident_severity"),
        Index("ix_incidents_created_id", "created_at", "id"),
    )


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"))
    status: Mapped[str] = mapped_column(String(24), default="QUEUED", nullable=False)
    focus: Mapped[str | None] = mapped_column(String(500))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="ck_investigation_window"),
        CheckConstraint("status IN ('QUEUED', 'RUNNING', 'AWAITING_REVIEW', 'COMPLETED', 'FAILED', 'CANCELLED')", name="ck_investigation_status"),
    )


class InvestigationJob(Base):
    __tablename__ = "investigation_jobs"
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')", name="ck_job_status"),
        CheckConstraint("attempts >= 0", name="ck_job_attempts"),
        Index("ix_jobs_claim", "status", "available_at", "lease_until"),
    )


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_backend: Mapped[str] = mapped_column(String(120), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(32))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (CheckConstraint("kind IN ('LOG', 'TRACE', 'METRIC', 'CHANGE')", name="ck_evidence_kind"),)


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, index=True)
    explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    missing_evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    __table_args__ = (CheckConstraint("confidence IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_hypothesis_confidence"),)


class HypothesisEvidence(Base):
    __tablename__ = "hypothesis_evidence"
    hypothesis_id: Mapped[str] = mapped_column(ForeignKey("hypotheses.id"), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    relation: Mapped[str] = mapped_column(String(12), nullable=False)
    __table_args__ = (CheckConstraint("relation IN ('SUPPORTS', 'CONTRADICTS')", name="ck_hypothesis_evidence_relation"),)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, unique=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), nullable=False, unique=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    __table_args__ = (CheckConstraint("decision IN ('ACCEPTED', 'REJECTED', 'INCONCLUSIVE')", name="ck_review_decision"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),)
