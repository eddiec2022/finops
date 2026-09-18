from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.idle_resources import build_idle_resource_recommendations
from app.services.non_peak_scheduling import build_non_peak_scheduling_recommendations
from app.services.rightsizing import build_rightsizing_recommendations

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.get("/rightsizing")
def get_rightsizing_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_rightsizing_recommendations(db)


@router.get("/idle-resources")
def get_idle_resource_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_idle_resource_recommendations(db)


@router.get("/non-peak-scheduling")
def get_non_peak_scheduling_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_non_peak_scheduling_recommendations(db)
