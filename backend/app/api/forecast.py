import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.forecast import build_forecast

router = APIRouter(prefix="/api/v1/forecast", tags=["forecast"])


@router.get("")
def get_forecast(
    horizon_days: int = Query(90, ge=1),
    resource_group: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return build_forecast(
        db,
        horizon_days=horizon_days,
        resource_group=resource_group,
        resource_type=resource_type,
        resource_id=resource_id,
    )
