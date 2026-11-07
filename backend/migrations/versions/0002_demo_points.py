"""Separate configurable demo points from real station telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("demo_points",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("water_depth_cm", sa.Float(), nullable=False),
        sa.Column("warning_threshold_cm", sa.Float(), nullable=False),
        sa.Column("danger_threshold_cm", sa.Float(), nullable=False),
        sa.Column("exclusion_radius_m", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude > -90 AND latitude < 90"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180"),
        sa.CheckConstraint("water_depth_cm >= 0 AND water_depth_cm <= 10000"),
        sa.CheckConstraint("warning_threshold_cm >= 0 AND danger_threshold_cm > warning_threshold_cm AND danger_threshold_cm <= 10000"),
        sa.CheckConstraint("exclusion_radius_m > 0 AND exclusion_radius_m <= 1000"),
    )


def downgrade():
    op.drop_table("demo_points")
