"""merge case-drift duplicate resources, normalize external_resource_id casing

Revision ID: 2450695ea788
Revises: 0a3c0e882688
Create Date: 2026-09-21 16:00:00.000000

Task 17 found that Azure Resource Graph can return a previously-synced resource's
ARM id in different casing on a later sync (confirmed live: the NISE-DEV VM's id
changed from `.../NISE-RG/.../NISE-DEV` to `.../nise-rg/.../nise-dev` between Task
2's original sync and Task 17's re-sync). `upsert_resources` matched existing rows
by an exact, case-sensitive `external_resource_id` comparison, so the casing change
read as a brand new resource instead of an update - producing a second `resources`
row for one physical VM. `azure_inventory.map_resource` now lowercases
`external_resource_id` at write time (see that file), which prevents this going
forward. This migration cleans up every row the bug already affected - not
hardcoded to the one VM incident, so it also catches any other resource this same
drift hit that hasn't been noticed yet.

For each group of resources rows that collide on `lower(external_resource_id)`:
1. picks one canonical row - the one with existing cost_records (real historical
   financial data already correctly attributed), falling back to the earliest-
   created row if no group member has any cost_records;
2. reassigns cost_records and utilization_metrics from the other row(s) onto the
   canonical row wherever that doesn't collide with something the canonical already
   has (same cloud_account/date/charge_type, or same metric/timestamp) - preserving
   real data rather than discarding it;
3. drops any remaining rows that *do* collide - those are genuine duplicate
   readings of the same physical resource (the same metric at the same timestamp,
   or the same charge on the same day), not distinct data;
4. deletes the non-canonical resource row(s).

Finally, normalizes every remaining resources.external_resource_id to lowercase, so
the existing case-sensitive uq_resources_external_resource_id constraint continues
to do its job correctly now that "the same resource" can never be stored under two
different casings again.

This is a lossy data migration (it deletes rows) - downgrade() cannot restore the
merged/deleted data, so it's a documented no-op rather than a fake reversal.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2450695ea788"
down_revision: Union[str, None] = "0a3c0e882688"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    duplicate_groups = conn.execute(
        sa.text(
            """
            SELECT array_agg(id ORDER BY id) AS ids
            FROM resources
            GROUP BY lower(external_resource_id)
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    for (ids,) in duplicate_groups:
        canonical_row = conn.execute(
            sa.text(
                """
                SELECT r.id
                FROM resources r
                LEFT JOIN (
                    SELECT resource_id, count(*) AS cnt
                    FROM cost_records
                    WHERE resource_id = ANY(:ids)
                    GROUP BY resource_id
                ) c ON c.resource_id = r.id
                WHERE r.id = ANY(:ids)
                ORDER BY COALESCE(c.cnt, 0) DESC, r.created_at ASC, r.id ASC
                LIMIT 1
                """
            ),
            {"ids": ids},
        ).scalar_one()

        losers = [row_id for row_id in ids if row_id != canonical_row]

        for loser in losers:
            # Reassign cost_records that don't collide with what the canonical
            # resource already has for the same account/date/charge_type.
            conn.execute(
                sa.text(
                    """
                    UPDATE cost_records
                    SET resource_id = :canonical
                    WHERE resource_id = :loser
                      AND NOT EXISTS (
                          SELECT 1 FROM cost_records c2
                          WHERE c2.resource_id = :canonical
                            AND c2.cloud_account_id = cost_records.cloud_account_id
                            AND c2.date = cost_records.date
                            AND c2.charge_type = cost_records.charge_type
                      )
                    """
                ),
                {"canonical": canonical_row, "loser": loser},
            )
            # Any cost_records left on the loser are genuine duplicates (same
            # account/date/charge_type the canonical already has) - drop them.
            conn.execute(
                sa.text("DELETE FROM cost_records WHERE resource_id = :loser"),
                {"loser": loser},
            )

            # Same pattern for utilization_metrics, keyed on (metric_name, timestamp).
            conn.execute(
                sa.text(
                    """
                    UPDATE utilization_metrics
                    SET resource_id = :canonical
                    WHERE resource_id = :loser
                      AND NOT EXISTS (
                          SELECT 1 FROM utilization_metrics u2
                          WHERE u2.resource_id = :canonical
                            AND u2.metric_name = utilization_metrics.metric_name
                            AND u2.timestamp = utilization_metrics.timestamp
                      )
                    """
                ),
                {"canonical": canonical_row, "loser": loser},
            )
            conn.execute(
                sa.text("DELETE FROM utilization_metrics WHERE resource_id = :loser"),
                {"loser": loser},
            )

            conn.execute(sa.text("DELETE FROM resources WHERE id = :loser"), {"loser": loser})

    conn.execute(sa.text("UPDATE resources SET external_resource_id = lower(external_resource_id)"))


def downgrade() -> None:
    # Lossy: merged/deleted rows can't be reconstructed. Left as a documented no-op
    # rather than a fake reversal - reverting past this point means restoring from
    # a backup taken before it ran, not running alembic downgrade.
    pass
