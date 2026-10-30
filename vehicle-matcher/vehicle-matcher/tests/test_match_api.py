"""Tests for POST /api/v1/vehicles/match.

The inventory used here is defined in conftest.py (14 vehicles, #13 unavailable).
"""
import pytest


def models(response):
    return [m["model"] for m in response.json()["matches"]]


def ids(response):
    return [m["vehicle_id"] for m in response.json()["matches"]]


# ------------------------------------------------------- single criteria

def test_brand_matching(match):
    r = match({"brand": "Toyota"})
    assert r.status_code == 200
    body = r.json()
    # 6 available Toyotas (the unavailable Quantum is excluded)
    assert body["total_matches"] == 6
    assert all(m["make"] == "Toyota" and m["match_score"] == 100 for m in body["matches"])


def test_budget_matching_orders_exact_fits_first(match):
    r = match({"budget_max": 200000})
    assert r.status_code == 200
    matches = r.json()["matches"]
    # Four vehicles are within budget; the Polo (R219,900) is within the 10%
    # tolerance and earns half credit, so it is still returned but ranked last.
    assert [m["model"] for m in matches] == ["Polo Vivo", "Picanto", "Corolla", "Starlet", "Polo"]
    assert [m["match_score"] for m in matches] == [100, 100, 100, 100, 50]
    assert all(m["price"] <= 200000 for m in matches[:4])
    assert "over budget" in matches[-1]["mismatches"][0]


def test_transmission_matching(match):
    r = match({"transmission": "manual"})
    assert r.json()["total_matches"] == 5  # Quantum (manual) is unavailable
    assert all(m["transmission"] == "Manual" for m in r.json()["matches"])


def test_body_type_matching(match):
    r = match({"body_type": "SUV"})
    assert sorted(models(r)) == ["Creta", "Fortuner", "RAV4", "Urban Cruiser"]


def test_mileage_matching(match):
    r = match({"max_mileage": 50000})
    matches = r.json()["matches"]
    perfect = [m for m in matches if m["match_score"] == 100]
    assert sorted(m["model"] for m in perfect) == ["Creta", "Picanto", "Starlet", "Urban Cruiser"]
    assert all(m["mileage"] <= 50000 for m in perfect)
    # Polo (54k) and Ranger (52k) are within the 10% tolerance -> half credit.
    assert sorted(m["model"] for m in matches if m["match_score"] == 50) == ["Polo", "Ranger"]


def test_fuel_type_matching(match):
    r = match({"fuel_type": "Electric"})
    assert models(r) == ["i3"]


def test_min_year_matching(match):
    r = match({"min_year": 2021})
    assert r.json()["total_matches"] == 6
    assert all(m["year"] >= 2021 for m in r.json()["matches"])


# ------------------------------------------------------ multiple criteria

SPEC_EXAMPLE = {
    "budget_max": 250000, "brand": "Toyota", "transmission": "automatic",
    "body_type": "SUV", "max_mileage": 100000,
}


def test_multiple_criteria_perfect_matches_first(match):
    r = match(SPEC_EXAMPLE)
    assert r.status_code == 200
    matches = r.json()["matches"]
    # The two Toyota automatic SUVs under R250k and 100,000 km are perfect;
    # equal scores are tie-broken by lower price.
    assert [m["model"] for m in matches[:2]] == ["Urban Cruiser", "RAV4"]
    assert [m["match_score"] for m in matches[:2]] == [100, 100]


def test_results_are_ordered_by_score_descending(match):
    scores = [m["match_score"] for m in match(SPEC_EXAMPLE).json()["matches"]]
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) > 1  # genuinely a mix of full and partial matches


def test_response_shape_and_reasons(match):
    top = match(SPEC_EXAMPLE).json()["matches"][0]
    for key in ("vehicle_id", "make", "model", "year", "price", "mileage",
                "transmission", "body_type", "match_score", "reasons"):
        assert key in top
    assert top["reasons"] == [
        "Brand matches: Toyota",
        "Price is R20,100 below budget",
        "Automatic transmission",
        "SUV body type",
        "Mileage is 52,000 km below maximum",
    ]
    assert top["mismatches"] == []


def test_partial_match_explains_what_is_wrong(match):
    starlet = next(m for m in match(SPEC_EXAMPLE).json()["matches"] if m["model"] == "Starlet")
    assert starlet["match_score"] < 100
    assert "Transmission is Manual, not Automatic" in starlet["mismatches"]
    assert "Body type is Hatchback, not SUV" in starlet["mismatches"]


def test_response_echoes_interpreted_criteria(match):
    criteria = match(SPEC_EXAMPLE).json()["criteria"]
    assert criteria == {
        "budget_max": 250000, "brand": "Toyota", "transmission": "Automatic",
        "body_type": "SUV", "max_mileage": 100000,
    }


# -------------------------------------------------- optional requirements

@pytest.mark.parametrize(
    "body",
    [
        {"budget_max": 250000, "transmission": "automatic"},
        {"brand": "Toyota"},
        {"budget_max": 200000, "body_type": "Hatchback", "max_mileage": 80000},
    ],
)
def test_optional_criteria_examples_from_the_brief(match, body):
    r = match(body)
    assert r.status_code == 200
    assert r.json()["total_matches"] > 0


def test_hatchback_budget_mileage_example(match):
    r = match({"budget_max": 200000, "body_type": "Hatchback", "max_mileage": 80000})
    matches = r.json()["matches"]
    # Picanto and Starlet fit everything. Polo Vivo is exactly 10% over on mileage
    # (half credit on that criterion); Polo is within 10% over on price.
    assert [m["model"] for m in matches[:4]] == ["Picanto", "Starlet", "Polo Vivo", "Polo"]
    assert [m["match_score"] for m in matches[:4]] == [100, 100, 90, 75]


# -------------------------------------------- no matches / exclusions

def test_no_matching_vehicles_returns_empty_list(match):
    r = match({"brand": "Ferrari"})
    assert r.status_code == 200
    assert r.json()["total_matches"] == 0
    assert r.json()["matches"] == []


def test_impossible_budget_returns_no_matches(match):
    r = match({"budget_max": 1000})
    assert r.status_code == 200 and r.json()["total_matches"] == 0


def test_unavailable_vehicles_are_never_returned(match):
    r = match({"body_type": "Minivan"})  # the only minivan (Quantum) is unavailable
    assert r.json()["total_matches"] == 0
    assert 13 not in ids(match({"brand": "Toyota"}))


def test_limit_caps_results_but_not_total(match):
    r = match({"brand": "Toyota", "limit": 2})
    assert r.json()["total_matches"] == 6
    assert len(r.json()["matches"]) == 2


def test_min_score_filters_weak_matches(match):
    r = match({"brand": "Toyota", "budget_max": 200000, "min_score": 100})
    assert models(r) == ["Corolla", "Starlet"]


# --------------------------------------------------- fuzzy / bonus features

def test_case_and_alias_variations_give_identical_results(match):
    baseline = ids(match({"brand": "Toyota", "transmission": "Automatic"}))
    assert baseline
    for brand, transmission in [("toyota", "automatic"), ("TOYOTA", "AUTO"), ("  Toyota ", "auto")]:
        assert ids(match({"brand": brand, "transmission": transmission})) == baseline


def test_brand_typo_and_alias_resolution(match):
    assert ids(match({"brand": "Toyata"})) == ids(match({"brand": "Toyota"}))
    assert set(models(match({"brand": "VW"}))) == {"Polo", "Polo Vivo"}
    assert models(match({"brand": "merc"})) == ["C200"]


def test_body_type_aliases(match):
    assert ids(match({"body_type": "hatch"})) == ids(match({"body_type": "Hatchback"}))
    assert models(match({"body_type": "pickup"})) == ["Hilux", "Ranger"]  # both perfect; cheaper first


def test_natural_language_query(match):
    r = match({"query": "I need an automatic Toyota SUV under R250k"})
    assert r.status_code == 200
    assert r.json()["criteria"] == {
        "budget_max": 250000.0, "brand": "Toyota", "transmission": "Automatic", "body_type": "SUV",
    }
    assert models(r)[:2] == ["Urban Cruiser", "RAV4"]


def test_explicit_fields_override_the_query(match):
    r = match({"query": "Toyota SUV", "brand": "Ford"})
    assert r.json()["criteria"]["brand"] == "Ford"


def test_unintelligible_query_is_rejected(match):
    r = match({"query": "hello there"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


# ------------------------------------------------------ invalid requests

@pytest.mark.parametrize(
    "body, expected",
    [
        ({}, "at least one search criterion"),
        ({"limit": 5}, "at least one search criterion"),  # control fields are not criteria
        ({"budget_max": -1}, "budget_max must be greater than 0"),
        ({"budget_max": 0}, "budget_max must be greater than 0"),
        ({"budget_max": "250000"}, "budget_max must be a number"),
        ({"budget_max": True}, "budget_max must be a number"),
        ({"budget_max": None, "brand": None}, "at least one search criterion"),
        ({"max_mileage": -5}, "max_mileage must be greater than or equal to 0"),
        ({"max_mileage": 100.5}, "max_mileage must be a whole number"),
        ({"max_mileage": "lots"}, "max_mileage must be a whole number"),
        ({"min_year": 1899}, "min_year must be between"),
        ({"min_year": 2999}, "min_year must be between"),
        ({"min_year": "2020"}, "min_year must be a whole number"),
        ({"transmission": "cvx"}, "transmission must be one of: Automatic, Manual"),
        ({"transmission": 5}, "transmission must be a string"),
        ({"body_type": "spaceship"}, "body_type must be one of"),
        ({"fuel_type": "water"}, "fuel_type must be one of"),
        ({"brand": ""}, "brand must not be empty"),
        ({"brand": "   "}, "brand must not be empty"),
        ({"brand": 123}, "brand must be a string"),
        ({"unknown_field": 1}, "unknown_field is not a recognised field"),
        ({"brand": "Toyota", "limit": 0}, "limit must be greater than or equal to 1"),
        ({"brand": "Toyota", "min_score": 101}, "min_score must be less than or equal to 100"),
    ],
)
def test_invalid_requests_return_clear_422(match, body, expected):
    r = match(body)
    assert r.status_code == 422, r.text
    payload = r.json()
    assert payload["error"] == "validation_error"
    assert expected in payload["message"]
    assert payload["details"], "details should list every problem"
    assert "detail" not in payload  # never FastAPI's raw default format


def test_all_validation_problems_are_reported_together(match):
    r = match({"budget_max": -1, "max_mileage": -1, "transmission": "cvx"})
    fields = {d["field"] for d in r.json()["details"]}
    assert fields == {"budget_max", "max_mileage", "transmission"}


def test_missing_body_is_rejected(client):
    r = client.post("/api/v1/vehicles/match")
    assert r.status_code == 422
    assert r.json()["message"] == "Request body is required"


def test_malformed_json_is_rejected(client):
    r = client.post("/api/v1/vehicles/match", content="{not json",
                    headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert r.json() == {
        "error": "validation_error",
        "message": "Request body is not valid JSON",
        "details": [{"field": "", "message": "Request body is not valid JSON"}],
    }


@pytest.mark.parametrize("body", [[], "text", 42])
def test_non_object_body_is_rejected(match, body):
    r = match(body)
    assert r.status_code == 422
    assert r.json()["message"] == "Request body must be a JSON object"


# ----------------------------------------------------------- misc

def test_unknown_route_returns_json_error(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


def test_wrong_method_returns_json_error(client):
    r = client.get("/api/v1/vehicles/match")
    assert r.status_code in (405, 422)
    assert "error" in r.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
