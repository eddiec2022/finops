"""resources name column, backfilled from raw_metadata

Revision ID: 0a3c0e882688
Revises: d7e2b5f91a44
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0a3c0e882688'
down_revision: Union[str, None] = 'd7e2b5f91a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Task 2's Resource Graph query already captures `name`, but
    # azure_inventory.map_resource only ever wrote it into the raw_metadata
    # JSONB blob, not a real column (flagged in Task 15). Nullable, matching
    # the other optional resource attributes (region, resource_group, sku) -
    # a resource without a usable name in raw_metadata should stay null
    # rather than fail the sync.
    op.add_column('resources', sa.Column('name', sa.String(), nullable=True))

    # Backfill already-synced rows from their own raw_metadata rather than
    # leaving them null until the next sync - raw_metadata->>'name' mirrors
    # exactly what map_resource now writes directly for new/updated rows.
    op.execute(
        """
        UPDATE resources
        SET name = raw_metadata ->> 'name'
        WHERE raw_metadata ? 'name'
        """
    )


def downgrade() -> None:
    op.drop_column('resources', 'name')
