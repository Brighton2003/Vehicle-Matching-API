"""Vehicle endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import APIError
from app.models import Vehicle
from app.schemas import (
    MatchedVehicle, MatchRequest, MatchResponse,
    VehicleListParams, VehicleListResponse, VehicleOut,
)
from app.services.matching import Criteria, rank_vehicles, resolve_brand
from app.services.nlp import parse_query

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

DbSession = Annotated[Session, Depends(get_db)]


def _known_makes(db: Session) -> list[str]:
    return list(db.scalars(select(Vehicle.make).distinct()))


@router.post(
    "/match",
    response_model=MatchResponse,
    summary="Find the vehicles that best match a customer's requirements",
)
def match_vehicles(request: MatchRequest, db: DbSession) -> MatchResponse:
    makes = _known_makes(db)

    # Start from the sentence (if any); explicit structured fields win over it.
    fields: dict = {}
    if request.query and request.query.strip():
        fields = parse_query(request.query, makes)
        if not fields and not any(
            v is not None for v in (request.budget_max, request.brand, request.transmission,
                                    request.body_type, request.fuel_type, request.max_mileage,
                                    request.min_year)
        ):
            raise APIError(
                422, "validation_error",
                "Could not find any vehicle requirements in 'query'. Try something like "
                "'automatic Toyota SUV under R250k'.",
            )
    for name in ("budget_max", "brand", "transmission", "body_type", "fuel_type", "max_mileage", "min_year"):
        value = getattr(request, name)
        if value is not None:
            fields[name] = value

    if fields.get("brand"):
        fields["brand"] = resolve_brand(fields["brand"], makes)
    criteria = Criteria(**fields)

    # Only vehicles that can actually be sold are candidates.
    available = db.scalars(select(Vehicle).where(Vehicle.availability.is_(True))).all()
    ranked = rank_vehicles(available, criteria, request.min_score)

    return MatchResponse(
        total_matches=len(ranked),
        matches=[
            MatchedVehicle(
                vehicle_id=r.vehicle.id,
                make=r.vehicle.make,
                model=r.vehicle.model,
                variant=r.vehicle.variant,
                year=r.vehicle.year,
                price=r.vehicle.price,
                mileage=r.vehicle.mileage,
                fuel_type=r.vehicle.fuel_type,
                transmission=r.vehicle.transmission,
                body_type=r.vehicle.body_type,
                colour=r.vehicle.colour,
                match_score=r.score,
                reasons=r.reasons,
                mismatches=r.mismatches,
            )
            for r in ranked[: request.limit]
        ],
        criteria=criteria.as_dict(),
    )


_SORT_COLUMNS = {
    "id": Vehicle.id,
    "price": Vehicle.price,
    "mileage": Vehicle.mileage,
    "year": Vehicle.year,
}


@router.get(
    "",
    response_model=VehicleListResponse,
    summary="List vehicles with optional filters and pagination",
)
def list_vehicles(params: Annotated[VehicleListParams, Query()], db: DbSession) -> VehicleListResponse:
    conditions = []
    if params.brand:
        conditions.append(func.lower(Vehicle.make) == resolve_brand(params.brand, _known_makes(db)).lower())
    if params.model:
        conditions.append(func.lower(Vehicle.model) == params.model.lower())
    if params.transmission:
        conditions.append(Vehicle.transmission == params.transmission.value)
    if params.body_type:
        conditions.append(Vehicle.body_type == params.body_type.value)
    if params.fuel_type:
        conditions.append(Vehicle.fuel_type == params.fuel_type.value)
    if params.min_price is not None:
        conditions.append(Vehicle.price >= params.min_price)
    if params.max_price is not None:
        conditions.append(Vehicle.price <= params.max_price)
    if params.max_mileage is not None:
        conditions.append(Vehicle.mileage <= params.max_mileage)
    if params.min_year is not None:
        conditions.append(Vehicle.year >= params.min_year)
    if params.max_year is not None:
        conditions.append(Vehicle.year <= params.max_year)
    if params.available is not None:
        conditions.append(Vehicle.availability.is_(params.available))

    total = db.scalar(select(func.count()).select_from(Vehicle).where(*conditions)) or 0

    column = _SORT_COLUMNS[params.sort_by]
    ordering = [column.desc() if params.order == "desc" else column.asc()]
    if params.sort_by != "id":
        ordering.append(Vehicle.id.asc())  # stable, deterministic pages

    rows = db.scalars(
        select(Vehicle)
        .where(*conditions)
        .order_by(*ordering)
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
    ).all()

    return VehicleListResponse(
        page=params.page,
        limit=params.limit,
        total=total,
        total_pages=-(-total // params.limit),  # ceiling division
        items=[VehicleOut.model_validate(v) for v in rows],
    )
