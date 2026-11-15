"""FastAPI application: ZEST fermentation experimental-data store + API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .errors import register_error_handlers
from .routers import datasets
from .routers.generic import all_crud_routers
from .storage import get_store

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Make sure the object-storage bucket exists before serving uploads.
    get_store().ensure_bucket()
    yield


app = FastAPI(
    title="ZEST Data API",
    version=__version__,
    description=(
        "Storage and REST access for ZEST fungal-fermentation experimental datasets. "
        "Dataset files are kept in object storage (MinIO); the relational schema "
        "covers the structured ZEST data model."
    ),
    root_path=settings.root_path,
    lifespan=lifespan,
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

# Dataset (object-storage) surface first, then generic CRUD for every diagram entity.
app.include_router(datasets.router)
for crud_router in all_crud_routers():
    app.include_router(crud_router)


@app.get("/health", tags=["meta"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "zest-data-api", "version": __version__}
