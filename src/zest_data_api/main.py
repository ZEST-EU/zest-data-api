"""FastAPI application: ZEST fermentation experimental-data store + API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .errors import register_error_handlers
from .routers import datasets, measurements
from .routers.generic import all_crud_routers

settings = get_settings()

app = FastAPI(
    title="ZEST Data API",
    version=__version__,
    description=(
        "Storage and REST access for ZEST fungal-fermentation experimental datasets. "
        "Implements the ZEST core data model, ingests SIM-01-format runs, and serves "
        "them for browsing and download."
    ),
    root_path=settings.root_path,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

register_error_handlers(app)

# User-facing surface first, then generic CRUD for every diagram entity.
app.include_router(datasets.router)
app.include_router(measurements.router)
for crud_router in all_crud_routers():
    app.include_router(crud_router)


@app.get("/health", tags=["meta"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "zest-data-api", "version": __version__}
