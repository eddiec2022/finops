from datetime import date

import pytest

from app.core.config import settings
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.aws_cost import map_cost_response, sync_aws_cost
from app.services.aws_inventory import get_or_create_aws_cloud_account
from app.services.forecast import build_forecast
from tests.fixtures.aws_cost import INSTANCE_ARN, RESPONSE_MIXED, make_response


def test_map_cost_response_resource_attributable_and_non_attributable():
    rows = map_cost_response(RESPONSE_MIXED)

    assert len(rows) == 3
    resource_row, usage_row, tax_row = rows

    assert resource_row["date"] == date(2026, 9, 15)
    assert resource_row["external_resource_id"] is not None
    assert resource_row["charge_type"] == "Usage"
    assert resource_row["amortized_cost"] == 12.3456
    assert resource_row["currency"] == "USD"

    # An empty resource-id group key (non-attributable charge) normalizes to
    # None, same convention as azure_cost.map_cost_response.
    assert usage_row["external_resource_id"] is None
    assert usage_row["charge_type"] == "Usage"

    assert tax_row["external_resource_id"] is None
    assert tax_row["charge_type"] == "Tax"
    assert tax_row["amortized_cost"] == 1.25


def _seed_ec2_resource(db_session):
    account = get_or_create_aws_cloud_account(db_session, settings.aws_account_id or "123456789012")
    resource = Resource(
        cloud_account_id=account.id,
        provider=Provider.AWS,
        external_resource_id=INSTANCE_ARN,
        resource_type="aws::ec2::instance",
        resource_group="EC2 instance",
        tags={},
        raw_metadata={},
    )
    db_session.add(resource)
    db_session.commit()
    return account, resource


def test_sync_aws_cost_creates_records(db_session, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "123456789012")
    account, resource = _seed_ec2_resource(db_session)

    def fake_fetch(account_id, lookback_days):
        return RESPONSE_MIXED

    summary = sync_aws_cost(db_session, fetch=fake_fetch)

    assert summary.found == 3
    assert summary.created == 3
    assert summary.updated == 0

    records = (
        db_session.query(CostRecord)
        .filter(CostRecord.cloud_account_id == account.id, CostRecord.date == date(2026, 9, 15))
        .all()
    )
    assert len(records) == 3

    # The fixture's resource ARN differs in case from what's stored on the
    # seeded Resource - confirms the case-insensitive match resolved it.
    resource_record = next(r for r in records if r.resource_id == resource.id)
    assert float(resource_record.amortized_cost) == 12.3456
    assert resource_record.charge_type == "Usage"

    non_attributable = [r for r in records if r.resource_id is None]
    assert len(non_attributable) == 2
    assert {r.charge_type for r in non_attributable} == {"Usage", "Tax"}


def test_sync_aws_cost_upsert_does_not_duplicate_on_overlapping_window(db_session, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "123456789012")
    account, resource = _seed_ec2_resource(db_session)

    def fake_fetch(account_id, lookback_days):
        return RESPONSE_MIXED

    sync_aws_cost(db_session, fetch=fake_fetch)

    def fake_fetch_overlapping(account_id, lookback_days):
        return make_response(
            [
                {
                    "Keys": [INSTANCE_ARN.upper(), "Usage"],
                    "Metrics": {"AmortizedCost": {"Amount": "99.99", "Unit": "USD"}},
                },
                {"Keys": ["", "Usage"], "Metrics": {"AmortizedCost": {"Amount": "5.00", "Unit": "USD"}}},
                {"Keys": ["", "Tax"], "Metrics": {"AmortizedCost": {"Amount": "1.25", "Unit": "USD"}}},
            ]
        )

    summary = sync_aws_cost(db_session, fetch=fake_fetch_overlapping)

    assert summary.found == 3
    assert summary.created == 0
    assert summary.updated == 3

    records = (
        db_session.query(CostRecord)
        .filter(CostRecord.cloud_account_id == account.id, CostRecord.date == date(2026, 9, 15))
        .all()
    )
    assert len(records) == 3  # still 3, not 6

    resource_record = next(r for r in records if r.resource_id == resource.id)
    assert float(resource_record.amortized_cost) == 99.99


def test_aws_cost_records_flow_into_existing_forecast_interface_unchanged(db_session, monkeypatch):
    """Confirms GOV-002 2.4's expectation directly: AWS cost data written by
    sync_aws_cost is readable by the same build_forecast/LinearBurnRateModel
    Azure uses, with zero forecast.py changes - only cloud_account_id (already a
    plain parameter) needs to point at the AWS account instead of Azure's."""
    monkeypatch.setattr(settings, "aws_account_id", "123456789012")
    account, resource = _seed_ec2_resource(db_session)

    def fake_fetch(account_id, lookback_days):
        return RESPONSE_MIXED

    sync_aws_cost(db_session, fetch=fake_fetch)

    result = build_forecast(db_session, horizon_days=7, cloud_account_id=account.id)

    assert result["insufficient_data"] is False
    assert result["daily_rate"] == pytest.approx(12.3456 + 5.00 + 1.25)
