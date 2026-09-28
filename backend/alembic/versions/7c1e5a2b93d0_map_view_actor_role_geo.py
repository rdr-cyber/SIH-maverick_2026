"""map view: actor investigation role + geolocation

Revision ID: 7c1e5a2b93d0
Revises: 1569534a6fe4
Create Date: 2026-09-28 02:40:00

Adds the MAP-VIEW columns to ``actors``: investigation_role (victim /
suspect / witness / person_of_interest / other), geo_lat, geo_lng and a
human-readable geo_label. All nullable — role NULL means "no role assigned",
geo NULL means "not geolocated", so existing rows stay valid untouched.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c1e5a2b93d0"
down_revision = "1569534a6fe4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("actors", sa.Column("investigation_role", sa.String(length=30), nullable=True))
    op.add_column("actors", sa.Column("geo_lat", sa.Float(), nullable=True))
    op.add_column("actors", sa.Column("geo_lng", sa.Float(), nullable=True))
    op.add_column("actors", sa.Column("geo_label", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("actors", "geo_label")
    op.drop_column("actors", "geo_lng")
    op.drop_column("actors", "geo_lat")
    op.drop_column("actors", "investigation_role")
