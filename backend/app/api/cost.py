import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.azure_cost import sync_cost
from app.services.forecast import build_daily_cost_history

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    summary = sync_cost(db)
    return {"found": summary.found, "created": summary.created, "updated": summary.updated}


@router.get("")
def get_daily_cost_history(
    resource_group: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return build_daily_cost_history(
        db, resource_group=resource_group, resource_type=resource_type, resource_id=resource_id
    )
