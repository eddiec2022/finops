import uuid
from datetime import date as date_type

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id"), nullable=True
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cloud_accounts.id"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    amortized_cost: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    granularity: Mapped[str] = mapped_column(String, nullable=False)
    # Azure Cost Management's dimension distinguishing Usage/Purchase/Refund/
    # UnusedReservation/etc - needed alongside resource_id in the upsert key,
    # since multiple non-resource-attributable charges (marketplace, support,
    # reservation purchases) can land on the same cloud_account_id/date with
    # resource_id both null. See the uq_cost_records_* migration for how NULL
    # resource_id is handled at the DB constraint level.
    charge_type: Mapped[str] = mapped_column(String, nullable=False)
