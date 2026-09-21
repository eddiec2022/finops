import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.aws_cost import sync_aws_cost
from app.services.azure_cost import sync_cost
from app.services.forecast import build_daily_cost_history

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    # Same pattern as inventory's sync dispatch - Azure's own call/behavior is
    # unchanged; AWS only runs, and only adds to the totals, when configured.
    summary = sync_cost(db)
    result = {"found": summary.found, "created": summary.created, "updated": summary.updated}
    if settings.aws_configured:
        aws_summary = sync_aws_cost(db)
        result["found"] += aws_summary.found
        result["created"] += aws_summary.created
        result["updated"] += aws_summary.updated
    return result


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
