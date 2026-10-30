"""Tests for the natural-language parser and the seed data / script."""
import pytest
from sqlalchemy import func, select

from app.enums import BodyType, FuelType, Transmission
from app.models import Vehicle
from app.seed_data import SAMPLE_VEHICLES
from app.services.nlp import parse_query
from scripts.seed import seed

MAKES = ["Toyota", "Volkswagen", "Ford", "Mercedes-Benz", "BMW"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I need an automatic Toyota SUV under R250k",
         {"transmission": Transmission.AUTOMATIC, "brand": "Toyota", "body_type": BodyType.SUV, "budget_max": 250000}),
        ("I'm looking for an automatic Toyota SUV under R250,000 with less than 100,000 km.",
         {"transmission": Transmission.AUTOMATIC, "brand": "Toyota", "body_type": BodyType.SUV,
          "budget_max": 250000, "max_mileage": 100000}),
        ("diesel bakkie, ford, max R450 000, under 120k km, 2018 or newer",
         {"fuel_type": FuelType.DIESEL, "body_type": BodyType.BAKKIE, "brand": "Ford",
          "budget_max": 450000, "max_mileage": 120000, "min_year": 2018}),
        ("a VW hatchback manual budget of R150000",
         {"brand": "Volkswagen", "body_type": BodyType.HATCHBACK,
          "transmission": Transmission.MANUAL, "budget_max": 150000}),
        ("merc sedan from 2019 below 90000 km",
         {"brand": "Mercedes-Benz", "body_type": BodyType.SEDAN, "min_year": 2019, "max_mileage": 90000}),
        ("R1.2m BMW", {"brand": "BMW", "budget_max": 1_200_000}),
    ],
)
def test_parse_query(text, expected):
    assert parse_query(text, MAKES) == expected


def test_parse_query_does_not_confuse_mileage_with_budget():
    parsed = parse_query("SUV with less than 80000 km", MAKES)
    assert parsed == {"body_type": BodyType.SUV, "max_mileage": 80000}


def test_parse_query_with_nothing_recognisable():
    assert parse_query("hello there", MAKES) == {}


# --------------------------------------------------------------- seeding

def test_sample_inventory_has_at_least_30_vehicles_with_all_fields():
    assert len(SAMPLE_VEHICLES) >= 30
    required = {"make", "model", "variant", "year", "price", "mileage",
                "fuel_type", "transmission", "body_type", "colour", "availability"}
    for row in SAMPLE_VEHICLES:
        assert required <= row.keys()
        assert row["price"] > 0 and row["mileage"] >= 0


def test_sample_inventory_uses_valid_vocabulary():
    assert {v["transmission"] for v in SAMPLE_VEHICLES} <= {t.value for t in Transmission}
    assert {v["body_type"] for v in SAMPLE_VEHICLES} <= {b.value for b in BodyType}
    assert {v["fuel_type"] for v in SAMPLE_VEHICLES} <= {f.value for f in FuelType}


def test_seed_is_idempotent_and_supports_reset(session_factory):
    with session_factory() as db:
        assert seed(db) == 0  # fixture already populated the table
        assert seed(db, reset=True) == len(SAMPLE_VEHICLES)
        assert db.scalar(select(func.count()).select_from(Vehicle)) == len(SAMPLE_VEHICLES)
        assert seed(db) == 0
