"""utilization_metrics (resource_id, metric_name, timestamp) unique constraint

Revision ID: c1a4f0e8b2d3
Revises: 80706cac4f93
Create Date: 2026-09-17 00:00:08.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c1a4f0e8b2d3'
down_revision: Union[str, None] = '80706cac4f93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The utilization connector upserts against this triple - a resource can only
    # have one reading per metric per hourly timestamp.
    op.create_unique_constraint(
        'uq_utilization_metrics_resource_metric_timestamp',
        'utilization_metrics',
        ['resource_id', 'metric_name', 'timestamp'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_utilization_metrics_resource_metric_timestamp', 'utilization_metrics', type_='unique'
    )
