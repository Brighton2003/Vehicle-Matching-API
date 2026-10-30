"""Unit tests for the scoring service (no HTTP, no database)."""
import pytest

from app.enums import BodyType, FuelType, Transmission
from app.models import Vehicle
from app.services.matching import (
    Criteria, WEIGHTS, rank_vehicles, resolve_brand, score_vehicle,
)


def car(**overrides) -> Vehicle:
    base = dict(
        id=1, make="Toyota", model="RAV4", variant="GX", year=2022, price=239900, mileage=72000,
        fuel_type="Petrol", transmission="Automatic", body_type="SUV", colour="Silver", availability=True,
    )
    return Vehicle(**{**base, **overrides})


def test_weights_follow_the_suggested_scheme():
    assert WEIGHTS["brand"] == 25 and WEIGHTS["budget"] == 25
    assert WEIGHTS["transmission"] == 15 and WEIGHTS["body_type"] == 15
    assert WEIGHTS["mileage"] == 10 and WEIGHTS["fuel_type"] == 10


def test_perfect_match_scores_100_regardless_of_how_many_criteria():
    assert score_vehicle(car(), Criteria(brand="Toyota")).score == 100
    full = Criteria(budget_max=250000, brand="Toyota", transmission=Transmission.AUTOMATIC,
                    body_type=BodyType.SUV, fuel_type=FuelType.PETROL, max_mileage=100000, min_year=2020)
    assert score_vehicle(car(), full).score == 100


def test_score_is_proportional_to_weights_of_requested_criteria():
    # brand (25) + transmission (15) requested; only the brand matches -> 25/40
    result = score_vehicle(car(transmission="Manual"),
                           Criteria(brand="Toyota", transmission=Transmission.AUTOMATIC))
    assert result.score == 63  # 62.5 rounds half up


def test_no_criteria_scores_zero():
    assert Criteria().is_empty()
    assert score_vehicle(car(), Criteria()).score == 0


def test_brand_comparison_ignores_case_and_punctuation():
    assert score_vehicle(car(make="Mercedes-Benz"), Criteria(brand="mercedes benz")).score == 100


@pytest.mark.parametrize(
    "price, expected_score",
    [(200000, 100), (250000, 100), (270000, 50), (275000, 50), (275001, 0), (400000, 0)],
)
def test_budget_scoring_boundaries(price, expected_score):
    assert score_vehicle(car(price=price), Criteria(budget_max=250000)).score == expected_score


@pytest.mark.parametrize(
    "mileage, expected_score",
    [(0, 100), (100000, 100), (110000, 50), (110001, 0)],
)
def test_mileage_scoring_boundaries(mileage, expected_score):
    assert score_vehicle(car(mileage=mileage), Criteria(max_mileage=100000)).score == expected_score


def test_explanations_for_budget_and_mileage():
    r = score_vehicle(car(price=239900, mileage=85000), Criteria(budget_max=250000, max_mileage=100000))
    assert r.reasons == ["Price is R10,100 below budget", "Mileage is 15,000 km below maximum"]
    r = score_vehicle(car(price=250000, mileage=100000), Criteria(budget_max=250000, max_mileage=100000))
    assert r.reasons == ["Price is exactly on budget", "Mileage is exactly at maximum"]
    r = score_vehicle(car(price=260000), Criteria(budget_max=250000))
    assert r.mismatches == ["Price is R10,000 over budget (within 10% tolerance)"]


def test_year_criterion():
    assert score_vehicle(car(year=2019), Criteria(min_year=2020)).score == 0
    assert score_vehicle(car(year=2020), Criteria(min_year=2020)).score == 100


def test_rank_filters_by_min_score_and_breaks_ties_deterministically():
    cheap = car(id=1, price=100000)
    dearer = car(id=2, price=120000)
    same_price_more_km = car(id=3, price=100000, mileage=90000)
    weak = car(id=4, make="Ford", transmission="Manual", body_type="Hatchback")
    criteria = Criteria(brand="Toyota", transmission=Transmission.AUTOMATIC, body_type=BodyType.SUV)
    ranked = rank_vehicles([dearer, weak, same_price_more_km, cheap], criteria)
    assert [r.vehicle.id for r in ranked] == [1, 3, 2]  # price asc, then mileage asc; weak (score 0) dropped
    assert rank_vehicles([weak], criteria, min_score=0) == []  # a zero score is never a match


@pytest.mark.parametrize(
    "text, expected",
    [
        ("toyota", "Toyota"), ("TOYOTA", "Toyota"), ("  Toyota ", "Toyota"),
        ("vw", "Volkswagen"), ("VW", "Volkswagen"), ("merc", "Mercedes-Benz"),
        ("mercedes benz", "Mercedes-Benz"), ("Toyata", "Toyota"), ("Volkswagon", "Volkswagen"),
        ("Ferrari", "Ferrari"),
    ],
)
def test_resolve_brand(text, expected):
    makes = ["Toyota", "Volkswagen", "Mercedes-Benz", "Ford", "BMW"]
    assert resolve_brand(text, makes) == expected
