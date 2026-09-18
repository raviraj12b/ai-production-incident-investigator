"""Initial product schema, separate from the Step 7C simulator.

Revision ID: phase05_0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "phase05_0001"
down_revision = None
branch_labels = None
depends_on = None


def id_col():
    return sa.Column("id", sa.String(36), primary_key=True)


def timestamp(name, nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade():
    op.create_table(
        "incidents", id_col(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        timestamp("window_start"), timestamp("window_end"),
        timestamp("created_at"), timestamp("updated_at"),
        sa.CheckConstraint("window_end > window_start", name="ck_incident_window"),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_incident_status"),
        sa.CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_incident_severity"),
    )
    op.create_index("ix_incidents_service", "incidents", ["service"])
    op.create_index("ix_incidents_created_id", "incidents", ["created_at", "id"])

    op.create_table(
        "investigations", id_col(),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("investigations.id")),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("focus", sa.String(500)),
        timestamp("window_start"), timestamp("window_end"), timestamp("created_at"),
        timestamp("started_at", nullable=True), timestamp("finished_at", nullable=True),
        sa.Column("error", sa.String(500)),
        sa.CheckConstraint("window_end > window_start", name="ck_investigation_window"),
        sa.CheckConstraint("status IN ('QUEUED', 'RUNNING', 'AWAITING_REVIEW', 'COMPLETED', 'FAILED', 'CANCELLED')", name="ck_investigation_status"),
    )
    op.create_index("ix_investigations_incident_id", "investigations", ["incident_id"])
    op.create_table(
        "investigation_jobs",
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        timestamp("available_at"), timestamp("lease_until", nullable=True),
        sa.Column("worker_id", sa.String(100)), timestamp("updated_at"),
        sa.CheckConstraint("status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')", name="ck_job_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_job_attempts"),
    )
    op.create_index("ix_jobs_claim", "investigation_jobs", ["status", "available_at", "lease_until"])

    op.create_table(
        "evidence", id_col(),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), timestamp("observed_at"),
        sa.Column("service", sa.String(120), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("source_backend", sa.String(120), nullable=False),
        sa.Column("source_ref", sa.String(500), nullable=False),
        sa.Column("trace_id", sa.String(32)), timestamp("captured_at"),
        sa.CheckConstraint("kind IN ('LOG', 'TRACE', 'METRIC', 'CHANGE')", name="ck_evidence_kind"),
    )
    op.create_index("ix_evidence_investigation_id", "evidence", ["investigation_id"])
    op.create_table(
        "hypotheses", id_col(),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("explanation", sa.String(2000), nullable=False),
        sa.Column("confidence", sa.String(8), nullable=False),
        sa.Column("missing_evidence", sa.JSON(), nullable=False),
        sa.CheckConstraint("confidence IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_hypothesis_confidence"),
    )
    op.create_index("ix_hypotheses_investigation_id", "hypotheses", ["investigation_id"])
    op.create_table(
        "hypothesis_evidence",
        sa.Column("hypothesis_id", sa.String(36), sa.ForeignKey("hypotheses.id"), primary_key=True),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidence.id"), primary_key=True),
        sa.Column("relation", sa.String(12), nullable=False),
        sa.CheckConstraint("relation IN ('SUPPORTS', 'CONTRADICTS')", name="ck_hypothesis_evidence_relation"),
    )
    op.create_table(
        "reports", id_col(),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False, unique=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("uncertainty", sa.Text(), nullable=False), timestamp("created_at"),
    )
    op.create_table(
        "reviews", id_col(),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False, unique=True),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reviewer", sa.String(120), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False), timestamp("created_at"),
        sa.CheckConstraint("decision IN ('ACCEPTED', 'REJECTED', 'INCONCLUSIVE')", name="ck_review_decision"),
    )
    op.create_table(
        "audit_events", id_col(),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False), timestamp("created_at"),
    )
    op.create_index("ix_audit_events_incident_id", "audit_events", ["incident_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )


def downgrade():
    for name in (
        "idempotency_records", "audit_events", "reviews", "reports",
        "hypothesis_evidence", "hypotheses", "evidence",
        "investigation_jobs", "investigations", "incidents",
    ):
        op.drop_table(name)
