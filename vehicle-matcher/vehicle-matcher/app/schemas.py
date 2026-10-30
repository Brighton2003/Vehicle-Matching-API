"""Pydantic request / response schemas (this is where input validation lives).

Validator messages for fields are phrased to follow the field name, e.g.
"must be greater than 0", because the error handler renders them as
"<field> <message>" (see app/errors.py).
"""
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.config import settings
from app.enums import (
    BODY_TYPE_ALIASES, FUEL_TYPE_ALIASES, TRANSMISSION_ALIASES,
    BodyType, FuelType, Transmission, normalise,
)

MIN_VEHICLE_YEAR = 1980


def _max_vehicle_year() -> int:
    return date.today().year + 1  # next year's models are sold before January


def _fuzzy_enum(aliases: dict, enum_cls: type):
    """Accept any spelling/case/alias of an enum value (Auto, AUTOMATIC, suv...)."""

    def check(value: Any):
        if value is None or isinstance(value, enum_cls):
            return value
        if not isinstance(value, str):
            raise ValueError("must be a string")
        member = normalise(value, aliases, enum_cls)
        if member is None:
            allowed = ", ".join(m.value for m in enum_cls)
            raise ValueError(f"must be one of: {allowed} (got '{value.strip()}')")
        return member

    return check


def _clean_text(value: Any):
    if value is None:
        return value
    if not isinstance(value, str):
        raise ValueError("must be a string")
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


TransmissionField = Annotated[Transmission | None, BeforeValidator(_fuzzy_enum(TRANSMISSION_ALIASES, Transmission))]
BodyTypeField = Annotated[BodyType | None, BeforeValidator(_fuzzy_enum(BODY_TYPE_ALIASES, BodyType))]
FuelTypeField = Annotated[FuelType | None, BeforeValidator(_fuzzy_enum(FUEL_TYPE_ALIASES, FuelType))]
TextField = Annotated[Annotated[str, Field(max_length=50)] | None, BeforeValidator(_clean_text)]


def _check_year(value: int | None) -> int | None:
    if value is not None and not (MIN_VEHICLE_YEAR <= value <= _max_vehicle_year()):
        raise ValueError(f"must be between {MIN_VEHICLE_YEAR} and {_max_vehicle_year()}")
    return value


# --------------------------------------------------------------- matching

class MatchRequest(BaseModel):
    """POST /api/v1/vehicles/match body. All criteria are optional, but at least one is required."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"budget_max": 250000, "brand": "Toyota", "transmission": "automatic",
                 "body_type": "SUV", "max_mileage": 100000},
                {"query": "I need an automatic Toyota SUV under R250k"},
            ]
        },
    )

    budget_max: Annotated[float, Field(gt=0, le=100_000_000, strict=True)] | None = None
    brand: TextField = None
    transmission: TransmissionField = None
    body_type: BodyTypeField = None
    fuel_type: FuelTypeField = None
    max_mileage: Annotated[int, Field(ge=0, le=2_000_000, strict=True)] | None = None
    min_year: Annotated[int, Field(strict=True)] | None = None
    query: Annotated[str, Field(max_length=500)] | None = Field(
        default=None, description="Free-text requirement, e.g. 'automatic Toyota SUV under R250k'."
    )
    limit: Annotated[int, Field(ge=1, le=50, strict=True)] = 10
    min_score: Annotated[int, Field(ge=0, le=100, strict=True)] = 50

    _year = field_validator("min_year")(_check_year)

    @model_validator(mode="after")
    def _require_a_criterion(self):
        supplied = (self.budget_max, self.brand, self.transmission, self.body_type,
                    self.fuel_type, self.max_mileage, self.min_year)
        if all(v is None for v in supplied) and not (self.query and self.query.strip()):
            raise ValueError(
                "Provide at least one search criterion: budget_max, brand, transmission, "
                "body_type, fuel_type, max_mileage, min_year or query"
            )
        return self


class MatchedVehicle(BaseModel):
    vehicle_id: int
    make: str
    model: str
    variant: str
    year: int
    price: int
    mileage: int
    fuel_type: str
    transmission: str
    body_type: str
    colour: str
    match_score: int
    reasons: list[str]
    mismatches: list[str]


class MatchResponse(BaseModel):
    total_matches: int
    matches: list[MatchedVehicle]
    criteria: dict[str, Any] = Field(description="The structured criteria that were actually used.")


# ---------------------------------------------------------------- listing

class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    make: str
    model: str
    variant: str
    year: int
    price: int
    mileage: int
    fuel_type: str
    transmission: str
    body_type: str
    colour: str
    availability: bool


class VehicleListParams(BaseModel):
    """Query-string filters for GET /api/v1/vehicles."""

    model_config = ConfigDict(extra="forbid")

    brand: TextField = None
    model: TextField = None
    transmission: TransmissionField = None
    body_type: BodyTypeField = None
    fuel_type: FuelTypeField = None
    min_price: Annotated[float, Field(ge=0)] | None = None
    max_price: Annotated[float, Field(gt=0)] | None = None
    max_mileage: Annotated[int, Field(ge=0)] | None = None
    min_year: int | None = None
    max_year: int | None = None
    available: bool | None = None
    sort_by: Literal["id", "price", "mileage", "year"] = "id"
    order: Literal["asc", "desc"] = "asc"
    page: Annotated[int, Field(ge=1)] = 1
    limit: Annotated[int, Field(ge=1, le=settings.max_page_limit)] = settings.default_page_limit

    _years = field_validator("min_year", "max_year")(_check_year)

    @model_validator(mode="after")
    def _ranges(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must not be greater than max_price")
        if self.min_year is not None and self.max_year is not None and self.min_year > self.max_year:
            raise ValueError("min_year must not be greater than max_year")
        return self


class VehicleListResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    items: list[VehicleOut]
