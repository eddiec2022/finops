from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.azure_cost import sync_cost

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    summary = sync_cost(db)
    return {"found": summary.found, "created": summary.created, "updated": summary.updated}
