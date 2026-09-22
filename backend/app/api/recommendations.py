from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.aws_idle_resources import build_aws_idle_resource_recommendations
from app.services.aws_non_peak_scheduling import build_aws_non_peak_scheduling_recommendations
from app.services.aws_reserved_instances import build_aws_reservation_recommendations
from app.services.aws_rightsizing import build_aws_rightsizing_recommendations
from app.services.idle_resources import build_idle_resource_recommendations
from app.services.non_peak_scheduling import build_non_peak_scheduling_recommendations
from app.services.reserved_instances import build_reservation_recommendations
from app.services.rightsizing import build_rightsizing_recommendations

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.get("/rightsizing")
def get_rightsizing_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    # Same pattern as sync dispatch (Task 19/20) - Azure's own result is
    # unchanged; AWS's recommendations are only appended when AWS is
    # configured.
    result = build_rightsizing_recommendations(db)
    if settings.aws_configured:
        result["recommendations"] = result["recommendations"] + build_aws_rightsizing_recommendations(db)["recommendations"]
    return result


@router.get("/idle-resources")
def get_idle_resource_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    result = build_idle_resource_recommendations(db)
    if settings.aws_configured:
        result["recommendations"] = (
            result["recommendations"] + build_aws_idle_resource_recommendations(db)["recommendations"]
        )
    return result


@router.get("/non-peak-scheduling")
def get_non_peak_scheduling_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    result = build_non_peak_scheduling_recommendations(db)
    if settings.aws_configured:
        result["recommendations"] = (
            result["recommendations"] + build_aws_non_peak_scheduling_recommendations(db)["recommendations"]
        )
    return result


@router.get("/reserved-instances")
def get_reservation_recommendations() -> dict[str, Any]:
    # Live call to each provider's own recommendation engine, not a DB read -
    # see reserved_instances.py for why this endpoint doesn't take a db
    # dependency the way the other three recommendation endpoints do.
    result = build_reservation_recommendations()
    if settings.aws_configured:
        result["recommendations"] = result["recommendations"] + build_aws_reservation_recommendations()["recommendations"]
    return result
