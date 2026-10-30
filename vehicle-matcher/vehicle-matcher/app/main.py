"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import SessionLocal, init_db
from app.errors import register_error_handlers
from app.routers import vehicles


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.auto_seed:
        from scripts.seed import seed

        with SessionLocal() as db:
            seed(db)  # no-op when the table already has rows
    yield


app = FastAPI(
    title="Vehicle Matching API",
    version="1.0.0",
    description="Match customer requirements to a dealership's vehicle inventory.",
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(vehicles.router)


@app.get("/health", tags=["meta"], summary="Liveness check")
def health() -> dict:
    return {"status": "ok"}
