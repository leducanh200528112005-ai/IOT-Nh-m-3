"""Initial station and measurement tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("warning_threshold_cm", sa.Float(), nullable=False),
        sa.Column("danger_threshold_cm", sa.Float(), nullable=False),
        sa.Column("exclusion_radius_m", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180"),
        sa.CheckConstraint("warning_threshold_cm >= 0 AND danger_threshold_cm > warning_threshold_cm"),
        sa.CheckConstraint("exclusion_radius_m > 0"),
    )
    op.create_table("measurements",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("station_id", sa.String(64), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("boot_id", sa.String(64), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("water_depth_cm", sa.Float()),
        sa.Column("sensor_ok", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("station_id", "boot_id", "seq", name="uq_measurement_message"),
        sa.CheckConstraint("seq >= 0"),
        sa.CheckConstraint("(sensor_ok AND water_depth_cm IS NOT NULL AND water_depth_cm >= 0) OR (NOT sensor_ok AND water_depth_cm IS NULL)"),
    )
    op.create_index("ix_measurements_station_received", "measurements", ["station_id", "received_at", "id"])


def downgrade():
    op.drop_table("measurements")
    op.drop_table("stations")
