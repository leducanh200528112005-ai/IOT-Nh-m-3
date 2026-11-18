"""Thêm trường tốc độ dâng nước phục vụ dự báo AI."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demo_points", sa.Column("rise_rate_cm_min", sa.Float(), nullable=False, server_default="0.0"))


def downgrade():
    op.drop_column("demo_points", "rise_rate_cm_min")
