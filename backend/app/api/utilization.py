from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.aws_utilization import sync_aws_utilization
from app.services.azure_utilization import sync_utilization

router = APIRouter(prefix="/api/v1/utilization", tags=["utilization"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    # Same pattern as inventory/cost sync dispatch (Task 19) - Azure's own
    # call/behavior is unchanged; AWS only runs, and only adds to the totals,
    # when configured.
    summary = sync_utilization(db)
    result = {
        "resources_processed": summary.resources_processed,
        "metrics_found": summary.metrics_found,
        "created": summary.created,
        "updated": summary.updated,
    }
    if settings.aws_configured:
        aws_summary = sync_aws_utilization(db)
        result["resources_processed"] += aws_summary.resources_processed
        result["metrics_found"] += aws_summary.metrics_found
        result["created"] += aws_summary.created
        result["updated"] += aws_summary.updated
    return result
