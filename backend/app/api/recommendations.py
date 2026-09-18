from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.rightsizing import build_rightsizing_recommendations

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.get("/rightsizing")
def get_rightsizing_recommendations(db: Session = Depends(get_db)) -> dict[str, Any]:
    return build_rightsizing_recommendations(db)
