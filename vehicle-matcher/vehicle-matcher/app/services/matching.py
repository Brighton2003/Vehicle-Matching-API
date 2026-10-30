"""Scoring logic: how well does a vehicle match a customer's requirements?

Design summary (the README has the full reasoning):

* Each requested criterion has a weight (WEIGHTS below, based on the suggested
  25/25/15/15/10/10 split, plus a minimum-year criterion).
* The score is normalised against the criteria the customer actually
  supplied, so a vehicle that satisfies everything requested scores 100 no
  matter how many criteria were provided.
* Budget and mileage give half credit when a vehicle is only slightly over the
  limit (within 10%), so near-misses rank above clear misses.
* Every criterion produces a human-readable explanation (reasons for what
  matched, mismatches for what did not).
"""
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import get_close_matches

from app.enums import BodyType, FuelType, Transmission, text_key
from app.models import Vehicle

WEIGHTS: dict[str, int] = {
    "brand": 25,
    "budget": 25,
    "transmission": 15,
    "body_type": 15,
    "mileage": 10,
    "fuel_type": 10,
    "year": 10,
}

OVER_LIMIT_TOLERANCE = 0.10  # budget / mileage may be exceeded by up to 10% for partial credit
PARTIAL_CREDIT = 0.5
DEFAULT_MIN_SCORE = 50

BRAND_ALIASES = {"vw": "Volkswagen", "chevy": "Chevrolet"}


@dataclass(frozen=True)
class Criteria:
    """Structured customer requirements. Every field is optional."""

    budget_max: float | None = None
    brand: str | None = None
    transmission: Transmission | None = None
    body_type: BodyType | None = None
    fuel_type: FuelType | None = None
    max_mileage: int | None = None
    min_year: int | None = None

    def is_empty(self) -> bool:
        return not self.as_dict()

    def as_dict(self) -> dict:
        """Only the criteria that were supplied, with enums as plain strings."""
        out: dict = {}
        for name in (
            "budget_max", "brand", "transmission", "body_type",
            "fuel_type", "max_mileage", "min_year",
        ):
            value = getattr(self, name)
            if value is not None:
                out[name] = value.value if hasattr(value, "value") else value
        return out

    def requested_weights(self) -> dict[str, int]:
        mapping = {
            "budget_max": "budget",
            "brand": "brand",
            "transmission": "transmission",
            "body_type": "body_type",
            "fuel_type": "fuel_type",
            "max_mileage": "mileage",
            "min_year": "year",
        }
        return {key: WEIGHTS[key] for field_name, key in mapping.items() if getattr(self, field_name) is not None}


@dataclass
class MatchResult:
    vehicle: Vehicle
    score: int
    reasons: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- helpers

def _rand(amount: float) -> str:
    return f"R{round(amount):,}"


def _km(amount: float) -> str:
    return f"{round(amount):,} km"


def resolve_brand(brand: str, known_makes: Iterable[str]) -> str:
    """Map a free-text brand to the canonical make used in the inventory.

    Handles case (toyota/TOYOTA), aliases (VW), unambiguous prefixes
    (merc -> Mercedes-Benz) and small typos (Toyata -> Toyota). Unknown brands
    are returned unchanged and will simply match nothing.
    """
    known = {text_key(m): m for m in known_makes}
    key = text_key(brand)
    if key in known:
        return known[key]
    alias = BRAND_ALIASES.get(key)
    if alias and text_key(alias) in known:
        return known[text_key(alias)]
    if len(key) >= 3:
        prefixed = [m for k, m in known.items() if k.startswith(key)]
        if len(prefixed) == 1:
            return prefixed[0]
    close = get_close_matches(key, list(known), n=1, cutoff=0.8)
    if close:
        return known[close[0]]
    return brand.strip()


def _within_tolerance(over: float, limit: float) -> bool:
    """True if exceeding ``limit`` by ``over`` is still inside the 10% tolerance."""
    return over <= limit * OVER_LIMIT_TOLERANCE + 1e-9


# ------------------------------------------------- per-criterion scoring
# Each returns (fraction of the weight earned: 0.0-1.0, explanation).

def _score_budget(price: int, budget: float) -> tuple[float, str]:
    if price <= budget:
        diff = budget - price
        return 1.0, "Price is exactly on budget" if diff == 0 else f"Price is {_rand(diff)} below budget"
    over = price - budget
    if _within_tolerance(over, budget):
        return PARTIAL_CREDIT, f"Price is {_rand(over)} over budget (within 10% tolerance)"
    return 0.0, f"Price is {_rand(over)} over budget"


def _score_mileage(mileage: int, maximum: int) -> tuple[float, str]:
    if mileage <= maximum:
        diff = maximum - mileage
        return 1.0, "Mileage is exactly at maximum" if diff == 0 else f"Mileage is {_km(diff)} below maximum"
    over = mileage - maximum
    if _within_tolerance(over, maximum):
        return PARTIAL_CREDIT, f"Mileage is {_km(over)} over maximum (within 10% tolerance)"
    return 0.0, f"Mileage is {_km(over)} over maximum"


def score_vehicle(vehicle: Vehicle, criteria: Criteria) -> MatchResult:
    """Score one vehicle against the supplied criteria (0-100)."""
    weights = criteria.requested_weights()
    total = sum(weights.values())
    if total == 0:
        return MatchResult(vehicle, 0)

    earned = 0.0
    reasons: list[str] = []
    mismatches: list[str] = []

    def record(key: str, fraction: float, text: str) -> None:
        nonlocal earned
        earned += weights[key] * fraction
        (reasons if fraction == 1.0 else mismatches).append(text)

    if criteria.brand is not None:
        ok = text_key(vehicle.make) == text_key(criteria.brand)
        record("brand", 1.0 if ok else 0.0,
               f"Brand matches: {vehicle.make}" if ok else f"Brand is {vehicle.make}, not {criteria.brand}")

    if criteria.budget_max is not None:
        record("budget", *_score_budget(vehicle.price, criteria.budget_max))

    if criteria.transmission is not None:
        ok = vehicle.transmission.lower() == criteria.transmission.value.lower()
        record("transmission", 1.0 if ok else 0.0,
               f"{vehicle.transmission} transmission" if ok
               else f"Transmission is {vehicle.transmission}, not {criteria.transmission.value}")

    if criteria.body_type is not None:
        ok = vehicle.body_type.lower() == criteria.body_type.value.lower()
        record("body_type", 1.0 if ok else 0.0,
               f"{vehicle.body_type} body type" if ok
               else f"Body type is {vehicle.body_type}, not {criteria.body_type.value}")

    if criteria.max_mileage is not None:
        record("mileage", *_score_mileage(vehicle.mileage, criteria.max_mileage))

    if criteria.fuel_type is not None:
        ok = vehicle.fuel_type.lower() == criteria.fuel_type.value.lower()
        record("fuel_type", 1.0 if ok else 0.0,
               f"{vehicle.fuel_type} fuel type" if ok
               else f"Fuel type is {vehicle.fuel_type}, not {criteria.fuel_type.value}")

    if criteria.min_year is not None:
        ok = vehicle.year >= criteria.min_year
        record("year", 1.0 if ok else 0.0,
               f"{vehicle.year} model (minimum {criteria.min_year})" if ok
               else f"{vehicle.year} model is older than {criteria.min_year}")

    score = int(100 * earned / total + 0.5)
    return MatchResult(vehicle, score, reasons, mismatches)


def rank_vehicles(
    vehicles: Iterable[Vehicle],
    criteria: Criteria,
    min_score: int = DEFAULT_MIN_SCORE,
) -> list[MatchResult]:
    """Score all vehicles, drop those below ``min_score`` and sort best-first.

    Ties are broken by lower price, then lower mileage, then id, so the
    ordering is fully deterministic.
    """
    results = [score_vehicle(v, criteria) for v in vehicles]
    results = [r for r in results if r.score >= min_score and r.score > 0]
    results.sort(key=lambda r: (-r.score, r.vehicle.price, r.vehicle.mileage, r.vehicle.id))
    return results
