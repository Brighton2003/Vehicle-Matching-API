"""Populate the vehicles table with the sample inventory.

Usage (from the project root):
    python -m scripts.seed            # seed only if the table is empty
    python -m scripts.seed --reset    # wipe the table and re-seed
"""
import argparse

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import Vehicle
from app.seed_data import SAMPLE_VEHICLES


def seed(db: Session, reset: bool = False) -> int:
    """Insert sample vehicles. Returns the number of rows inserted."""
    if reset:
        db.execute(delete(Vehicle))
        db.commit()
    elif db.scalar(select(func.count()).select_from(Vehicle)):
        return 0
    db.add_all(Vehicle(**row) for row in SAMPLE_VEHICLES)
    db.commit()
    return len(SAMPLE_VEHICLES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete existing vehicles first")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        inserted = seed(db, reset=args.reset)
    if inserted:
        print(f"Seeded {inserted} vehicles.")
    else:
        print("Vehicles table already populated; nothing to do (use --reset to re-seed).")


if __name__ == "__main__":
    main()
