"""Retain indexing history after a Google connection is disconnected."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_preserve_history"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("indexing_attempts_connection_id_fkey", "indexing_attempts", type_="foreignkey")
    op.alter_column("indexing_attempts", "connection_id", existing_type=postgresql.UUID(), nullable=True)
    op.create_foreign_key(
        "fk_indexing_attempts_connection_id_google_connections",
        "indexing_attempts",
        "google_connections",
        ["connection_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Revert only when no history row has lost its connection reference. Never
    # delete or fabricate audit history to satisfy the old NOT NULL constraint.
    has_orphaned_history = op.get_bind().execute(
        sa.text("SELECT 1 FROM indexing_attempts WHERE connection_id IS NULL LIMIT 1")
    ).first()
    if has_orphaned_history:
        raise RuntimeError("Cannot downgrade: disconnected indexing history has no connection reference")
    op.drop_constraint("fk_indexing_attempts_connection_id_google_connections", "indexing_attempts", type_="foreignkey")
    op.alter_column("indexing_attempts", "connection_id", existing_type=postgresql.UUID(), nullable=False)
    op.create_foreign_key(
        "indexing_attempts_connection_id_fkey",
        "indexing_attempts",
        "google_connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )
