from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from azure.identity import ClientSecretCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource

RESOURCE_GRAPH_QUERY = (
    "Resources | project id, name, type, location, resourceGroup, tags, sku, properties"
)

# Different resource types surface their creation timestamp under different
# properties keys; check the ones we've seen (VMs, storage accounts, disks).
_CREATED_AT_KEYS = ("timeCreated", "creationTime", "createdTime")


@dataclass
class SyncSummary:
    found: int
    created: int
    updated: int


def fetch_resources(subscription_id: str) -> list[dict[str, Any]]:
    """Query Azure Resource Graph for every resource in the subscription, paging through results."""
    credential = ClientSecretCredential(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    client = ResourceGraphClient(credential)

    results: list[dict[str, Any]] = []
    skip_token: str | None = None
    while True:
        request = QueryRequest(
            subscriptions=[subscription_id],
            query=RESOURCE_GRAPH_QUERY,
            options=QueryRequestOptions(skip_token=skip_token) if skip_token else None,
        )
        response = client.resources(request)
        results.extend(response.data)
        skip_token = response.skip_token
        if not skip_token:
            break
    return results


def _extract_sku(row: dict[str, Any], properties: dict[str, Any]) -> str | None:
    sku = row.get("sku")
    if isinstance(sku, dict):
        return sku.get("name")
    if isinstance(sku, str):
        return sku
    # VMs don't carry a top-level `sku` in Resource Graph - size lives in properties.
    hardware_profile = properties.get("hardwareProfile") if isinstance(properties, dict) else None
    if isinstance(hardware_profile, dict):
        return hardware_profile.get("vmSize")
    return None


def map_resource(row: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Azure Resource Graph row into the normalized `resources` schema."""
    properties = row.get("properties") or {}
    sku_name = _extract_sku(row, properties)
    created_at = None
    if isinstance(properties, dict):
        for key in _CREATED_AT_KEYS:
            value = properties.get(key)
            if value:
                try:
                    created_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                except ValueError:
                    created_at = None
                break

    mapped: dict[str, Any] = {
        "provider": Provider.AZURE,
        "external_resource_id": row["id"],
        "resource_type": row.get("type", ""),
        "region": row.get("location"),
        "resource_group": row.get("resourceGroup"),
        "tags": row.get("tags") or {},
        "sku": sku_name,
        "raw_metadata": row,
    }
    # Only set created_at when we found a real value - otherwise let the model
    # default (now()) apply on create, and leave the existing value on update.
    if created_at is not None:
        mapped["created_at"] = created_at
    return mapped


def get_or_create_cloud_account(db: Session, subscription_id: str) -> CloudAccount:
    account = (
        db.query(CloudAccount)
        .filter_by(provider=Provider.AZURE, external_id=subscription_id)
        .one_or_none()
    )
    if account is None:
        account = CloudAccount(
            provider=Provider.AZURE,
            external_id=subscription_id,
            display_name=f"Azure Subscription {subscription_id}",
        )
        db.add(account)
        db.flush()
    return account


def upsert_resources(
    db: Session, cloud_account: CloudAccount, mapped_resources: list[dict[str, Any]]
) -> tuple[int, int]:
    created = 0
    updated = 0
    for mapped in mapped_resources:
        existing = (
            db.query(Resource)
            .filter_by(external_resource_id=mapped["external_resource_id"])
            .one_or_none()
        )
        if existing is None:
            db.add(Resource(cloud_account_id=cloud_account.id, **mapped))
            created += 1
        else:
            for key, value in mapped.items():
                setattr(existing, key, value)
            updated += 1
    db.commit()
    return created, updated


def sync_inventory(
    db: Session, fetch: Callable[[str], list[dict[str, Any]]] = fetch_resources
) -> SyncSummary:
    subscription_id = settings.azure_subscription_id
    raw_resources = fetch(subscription_id)
    cloud_account = get_or_create_cloud_account(db, subscription_id)
    mapped_resources = [map_resource(row) for row in raw_resources]
    created, updated = upsert_resources(db, cloud_account, mapped_resources)
    return SyncSummary(found=len(raw_resources), created=created, updated=updated)
