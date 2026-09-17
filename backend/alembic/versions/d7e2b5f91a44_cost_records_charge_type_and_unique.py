"""cost_records charge_type column and upsert uniqueness

Revision ID: d7e2b5f91a44
Revises: c1a4f0e8b2d3
Create Date: 2026-09-17 00:00:09.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd7e2b5f91a44'
down_revision: Union[str, None] = 'c1a4f0e8b2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cost_records', sa.Column('charge_type', sa.String(), nullable=False, server_default='Usage'))
    op.alter_column('cost_records', 'charge_type', server_default=None)

    # A plain UNIQUE constraint on (cloud_account_id, resource_id, date, charge_type)
    # would NOT actually enforce uniqueness when resource_id is NULL - Postgres
    # treats every NULL as distinct from every other NULL for uniqueness purposes,
    # so two non-resource-attributable charges with the same charge_type on the
    # same day would both be allowed through at the DB level even though the app's
    # upsert logic treats them as the same record. COALESCE-ing resource_id to a
    # fixed sentinel in an expression index closes that gap.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_cost_records_account_resource_date_chargetype
        ON cost_records (cloud_account_id, COALESCE(resource_id::text, ''), date, charge_type)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_cost_records_account_resource_date_chargetype")
    op.drop_column('cost_records', 'charge_type')
