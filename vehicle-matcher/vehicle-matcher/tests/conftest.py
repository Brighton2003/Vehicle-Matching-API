"""Shared fixtures: an isolated in-memory database with a small, known inventory."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, make_engine
from app.main import app
from app.models import Vehicle

_COLUMNS = (
    "make", "model", "variant", "year", "price", "mileage",
    "fuel_type", "transmission", "body_type", "colour", "availability",
)

# Ids are assigned 1..14 in this order. Kept small so expected results can be
# worked out by hand (see the comments in the tests).
TEST_INVENTORY = [
    ("Toyota", "RAV4", "2.0 GX", 2022, 239900, 72000, "Petrol", "Automatic", "SUV", "Silver", True),           # 1
    ("Toyota", "Urban Cruiser", "1.5 XR", 2021, 229900, 48000, "Petrol", "Automatic", "SUV", "White", True),   # 2
    ("Toyota", "Fortuner", "2.8 GD-6", 2019, 549900, 89000, "Diesel", "Automatic", "SUV", "Grey", True),       # 3
    ("Toyota", "Starlet", "1.4 Xi", 2022, 199900, 35000, "Petrol", "Manual", "Hatchback", "Red", True),        # 4
    ("Toyota", "Hilux", "2.4 GD-6", 2020, 459900, 85000, "Diesel", "Manual", "Bakkie", "White", True),         # 5
    ("Volkswagen", "Polo", "1.0 TSI", 2020, 219900, 54000, "Petrol", "Automatic", "Hatchback", "Grey", True),  # 6
    ("Volkswagen", "Polo Vivo", "1.4", 2019, 149900, 88000, "Petrol", "Manual", "Hatchback", "White", True),   # 7
    ("Ford", "Ranger", "2.0 Wildtrak", 2021, 599900, 52000, "Diesel", "Automatic", "Bakkie", "Black", True),   # 8
    ("Hyundai", "Creta", "1.5 Exec", 2021, 279900, 44000, "Petrol", "Automatic", "SUV", "Grey", True),         # 9
    ("Kia", "Picanto", "1.2 Street", 2021, 159900, 29000, "Petrol", "Manual", "Hatchback", "Yellow", True),    # 10
    ("BMW", "i3", "Range Extender", 2018, 289900, 61000, "Electric", "Automatic", "Hatchback", "Blue", True),  # 11
    ("Toyota", "Corolla", "1.6 Prestige", 2017, 179900, 118000, "Petrol", "Manual", "Sedan", "Silver", True),  # 12
    ("Toyota", "Quantum", "2.7 GL", 2018, 399900, 142000, "Petrol", "Manual", "Minivan", "White", False),      # 13 (unavailable)
    ("Mercedes-Benz", "C200", "AMG Line", 2018, 389900, 82000, "Petrol", "Automatic", "Sedan", "Silver", True),  # 14
]


@pytest.fixture()
def session_factory():
    engine = make_engine("sqlite://")  # fresh in-memory database per test
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all(Vehicle(**dict(zip(_COLUMNS, row))) for row in TEST_INVENTORY)
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager on purpose: that would run the startup
    # hook, which seeds the real (file-based) database.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def match(client):
    """Helper: POST a body to the match endpoint."""

    def _match(body, **kwargs):
        return client.post("/api/v1/vehicles/match", json=body, **kwargs)

    return _match
