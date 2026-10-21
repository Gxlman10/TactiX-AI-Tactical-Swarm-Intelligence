"""Reject negative roster positions without changing existing roster data."""

from alembic import op

revision = "70b4bceddc72"
down_revision = "0e3512262d31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint("ck_clubs_position_nonnegative", "clubs", "position >= 0")
    op.create_check_constraint("ck_players_position_nonnegative", "players", "position >= 0")


def downgrade():
    op.drop_constraint("ck_players_position_nonnegative", "players", type_="check")
    op.drop_constraint("ck_clubs_position_nonnegative", "clubs", type_="check")
