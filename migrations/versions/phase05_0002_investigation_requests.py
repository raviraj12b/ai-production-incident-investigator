"""Deduplicate investigation creation within an incident.

Revision ID: phase05_0002
Revises: phase05_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "phase05_0002"
down_revision = "phase05_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigation_requests",
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False, unique=True),
    )


def downgrade():
    op.drop_table("investigation_requests")
