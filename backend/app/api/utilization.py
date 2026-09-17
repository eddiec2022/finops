from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.azure_utilization import sync_utilization

router = APIRouter(prefix="/api/v1/utilization", tags=["utilization"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    summary = sync_utilization(db)
    return {
        "resources_processed": summary.resources_processed,
        "metrics_found": summary.metrics_found,
        "created": summary.created,
        "updated": summary.updated,
    }
