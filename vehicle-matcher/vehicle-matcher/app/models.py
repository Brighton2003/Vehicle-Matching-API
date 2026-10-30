"""SQLAlchemy ORM models."""
from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_vehicle_price_nonneg"),
        CheckConstraint("mileage >= 0", name="ck_vehicle_mileage_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    make: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(50))
    variant: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer, index=True)
    price: Mapped[int] = mapped_column(Integer, index=True)  # whole rand (ZAR)
    mileage: Mapped[int] = mapped_column(Integer)  # kilometres
    fuel_type: Mapped[str] = mapped_column(String(20), index=True)
    transmission: Mapped[str] = mapped_column(String(20), index=True)
    body_type: Mapped[str] = mapped_column(String(20), index=True)
    colour: Mapped[str] = mapped_column(String(30))
    availability: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Vehicle {self.id} {self.year} {self.make} {self.model}>"
