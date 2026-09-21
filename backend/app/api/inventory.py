from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.aws_inventory import sync_aws_inventory
from app.services.azure_inventory import sync_inventory
from app.services.inventory_listing import build_resource_list

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    # Azure sync call/behavior is completely unchanged from before Task 19 - the
    # AWS sync only runs, and only adds to the totals below, when AWS is actually
    # configured (Task 20's live account). With AWS unset, this endpoint's
    # behavior and response are byte-identical to pre-Task-19.
    summary = sync_inventory(db)
    result = {"found": summary.found, "created": summary.created, "updated": summary.updated}
    if settings.aws_configured:
        aws_summary = sync_aws_inventory(db)
        result["found"] += aws_summary.found
        result["created"] += aws_summary.created
        result["updated"] += aws_summary.updated
    return result


@router.get("")
def get_resources(
    resource_group: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return build_resource_list(db, resource_group=resource_group)
