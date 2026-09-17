"""resources external_resource_id unique constraint

Revision ID: 80706cac4f93
Revises: a2e358174b8e
Create Date: 2026-09-16 00:00:07.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '80706cac4f93'
down_revision: Union[str, None] = 'a2e358174b8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Azure resource IDs (and their AWS/GCP equivalents) are globally unique,
    # so this is the natural key the inventory connector upserts against.
    op.create_unique_constraint(
        'uq_resources_external_resource_id', 'resources', ['external_resource_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_resources_external_resource_id', 'resources', type_='unique')
