import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource import Resource
from app.services.azure_inventory import get_or_create_cloud_account


def build_resource_list(
    db: Session,
    resource_group: str | None = None,
    cloud_account_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Compute-on-read listing of synced resources, for drill-down discovery.

    Added for Task 15: /api/v1/cost and /api/v1/forecast already accept
    resource_group/resource_type filters, but nothing exposed what resource
    groups or resources actually exist to filter down to. Same
    single-subscription cloud_account_id convention as forecast.py/rightsizing.py.
    """
    if cloud_account_id is None:
        cloud_account_id = get_or_create_cloud_account(db, settings.azure_subscription_id).id

    query = db.query(Resource).filter(Resource.cloud_account_id == cloud_account_id)
    if resource_group:
        query = query.filter(Resource.resource_group == resource_group)
    resources = query.order_by(Resource.resource_group, Resource.resource_type, Resource.external_resource_id).all()

    return {
        "resources": [
            {
                "resource_id": str(resource.id),
                "external_resource_id": resource.external_resource_id,
                "name": resource.name,
                "resource_group": resource.resource_group,
                "resource_type": resource.resource_type,
                "region": resource.region,
            }
            for resource in resources
        ],
    }
