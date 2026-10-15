"""Initial OAuth and indexing schema."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email", sa.String(320), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("oauth_transactions", sa.Column("state_hash", sa.String(64), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("verifier", sa.Text(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("google_connections", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("google_sub", sa.String(255), nullable=False), sa.Column("email", sa.String(320), nullable=False), sa.Column("access_token_enc", sa.Text(), nullable=False), sa.Column("refresh_token_enc", sa.Text(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("scopes", postgresql.JSONB(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="connected"), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("user_id", "google_sub"))
    op.create_index("ix_google_connections_user_id", "google_connections", ["user_id"])
    op.create_table("indexing_attempts", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("google_connections.id", ondelete="CASCADE"), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("url", sa.Text(), nullable=False), sa.Column("site_url", sa.Text(), nullable=False), sa.Column("action", sa.String(32), nullable=False), sa.Column("page_type", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("response", postgresql.JSONB()), sa.Column("safe_error", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("user_id", "idempotency_key"))
    op.create_index("ix_indexing_attempts_user_id", "indexing_attempts", ["user_id"])

def downgrade():
    op.drop_table("indexing_attempts"); op.drop_index("ix_google_connections_user_id", table_name="google_connections"); op.drop_table("google_connections"); op.drop_table("oauth_transactions"); op.drop_table("users")
