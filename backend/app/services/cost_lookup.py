import uuid
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cost_record import CostRecord


def get_resource_daily_costs(db: Session, resource_id: uuid.UUID) -> list[tuple[date, float]]:
    query = (
        db.query(CostRecord.date, func.sum(CostRecord.amortized_cost))
        .filter(CostRecord.resource_id == resource_id)
        .group_by(CostRecord.date)
        .order_by(CostRecord.date)
    )
    return [(row_date, float(total)) for row_date, total in query.all()]
