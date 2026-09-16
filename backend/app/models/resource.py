import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.provider import Provider


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cloud_accounts.id"), nullable=False
    )
    provider: Mapped[Provider] = mapped_column(Enum(Provider, name="provider"), nullable=False)
    external_resource_id: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_group: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    raw_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    cloud_account: Mapped["CloudAccount"] = relationship(back_populates="resources")
