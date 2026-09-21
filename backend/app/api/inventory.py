from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.azure_inventory import sync_inventory
from app.services.inventory_listing import build_resource_list

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    summary = sync_inventory(db)
    return {"found": summary.found, "created": summary.created, "updated": summary.updated}


@router.get("")
def get_resources(
    resource_group: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return build_resource_list(db, resource_group=resource_group)
