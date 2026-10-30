"""Tests for GET /api/v1/vehicles (filtering, sorting, pagination)."""
import pytest

URL = "/api/v1/vehicles"


def get(client, query=""):
    return client.get(f"{URL}?{query}" if query else URL)


def models(response):
    return [v["model"] for v in response.json()["items"]]


# ------------------------------------------------------------ listing

def test_lists_all_vehicles_with_default_pagination(client):
    r = get(client)
    assert r.status_code == 200
    body = r.json()
    assert (body["page"], body["limit"], body["total"], body["total_pages"]) == (1, 10, 14, 2)
    assert len(body["items"]) == 10
    assert {"id", "make", "model", "variant", "year", "price", "mileage", "fuel_type",
            "transmission", "body_type", "colour", "availability"} <= body["items"][0].keys()


# --------------------------------------------------------------- filters

def test_filter_by_brand_includes_unavailable_stock(client):
    r = get(client, "brand=Toyota&limit=50")
    assert r.json()["total"] == 7  # the unavailable Quantum is listed too
    assert all(v["make"] == "Toyota" for v in r.json()["items"])


@pytest.mark.parametrize("brand", ["toyota", "TOYOTA", "Toyata"])
def test_brand_filter_is_fuzzy(client, brand):
    assert get(client, f"brand={brand}").json()["total"] == 7


def test_filter_example_from_the_brief(client):
    r = get(client, "max_price=250000&transmission=automatic")
    assert sorted(models(r)) == ["Polo", "RAV4", "Urban Cruiser"]
    assert all(v["price"] <= 250000 and v["transmission"] == "Automatic" for v in r.json()["items"])


def test_filter_by_body_type_and_fuel(client):
    assert get(client, "body_type=suv").json()["total"] == 4
    assert models(get(client, "fuel_type=electric")) == ["i3"]


def test_filter_by_price_mileage_and_year_ranges(client):
    r = get(client, "min_price=200000&max_price=250000")
    assert all(200000 <= v["price"] <= 250000 for v in r.json()["items"])
    assert r.json()["total"] == 3
    assert all(v["mileage"] <= 50000 for v in get(client, "max_mileage=50000").json()["items"])
    r = get(client, "min_year=2021&max_year=2021")
    assert all(v["year"] == 2021 for v in r.json()["items"])


def test_filter_by_model_and_availability(client):
    assert models(get(client, "model=hilux")) == ["Hilux"]
    r = get(client, "available=false")
    assert models(r) == ["Quantum"] and r.json()["items"][0]["availability"] is False
    assert get(client, "available=true").json()["total"] == 13


def test_combined_filters(client):
    r = get(client, "brand=Toyota&body_type=SUV&max_price=240000")
    assert sorted(models(r)) == ["RAV4", "Urban Cruiser"]


def test_no_results(client):
    body = get(client, "brand=Ferrari").json()
    assert body["total"] == 0 and body["total_pages"] == 0 and body["items"] == []


# ------------------------------------------------------------- sorting

def test_sorting(client):
    assert models(get(client, "sort_by=price&order=desc&limit=1")) == ["Ranger"]
    assert models(get(client, "sort_by=mileage&limit=1")) == ["Picanto"]
    prices = [v["price"] for v in get(client, "sort_by=price&limit=50").json()["items"]]
    assert prices == sorted(prices)


# ---------------------------------------------------------- pagination

def test_pagination_pages_are_complete_and_disjoint(client):
    seen = []
    for page in (1, 2, 3):
        r = get(client, f"page={page}&limit=5")
        assert r.json()["page"] == page and r.json()["total_pages"] == 3
        seen += [v["id"] for v in r.json()["items"]]
    assert len(seen) == 14 and len(set(seen)) == 14
    assert [len(get(client, f"page={p}&limit=5").json()["items"]) for p in (1, 2, 3)] == [5, 5, 4]


def test_page_beyond_the_end_is_empty_not_an_error(client):
    r = get(client, "page=99&limit=10")
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["total"] == 14


def test_pagination_is_stable_when_sorting_by_a_non_unique_column(client):
    # Several vehicles share a year; the id tie-breaker keeps pages consistent.
    ids = []
    for page in (1, 2, 3):
        ids += [v["id"] for v in get(client, f"sort_by=year&page={page}&limit=5").json()["items"]]
    assert len(set(ids)) == 14


# ------------------------------------------------------------ invalid

@pytest.mark.parametrize(
    "query, expected",
    [
        ("page=0", "page must be greater than or equal to 1"),
        ("page=abc", "page must be a whole number"),
        ("limit=0", "limit must be greater than or equal to 1"),
        ("limit=1000", "limit must be less than or equal to 100"),
        ("max_price=-5", "max_price must be greater than 0"),
        ("min_price=-5", "min_price must be greater than or equal to 0"),
        ("max_mileage=-1", "max_mileage must be greater than or equal to 0"),
        ("max_price=cheap", "max_price must be a number"),
        ("min_year=1800", "min_year must be between"),
        ("transmission=cvx", "transmission must be one of"),
        ("body_type=spaceship", "body_type must be one of"),
        ("available=maybe", "available must be true or false"),
        ("sort_by=colour", "sort_by must be one of"),
        ("order=sideways", "order must be one of"),
        ("bogus=1", "bogus is not a recognised field"),
        ("min_price=500&max_price=100", "min_price must not be greater than max_price"),
    ],
)
def test_invalid_query_parameters(client, query, expected):
    r = get(client, query)
    assert r.status_code == 422, r.text
    assert r.json()["error"] == "validation_error"
    assert expected in r.json()["message"]
