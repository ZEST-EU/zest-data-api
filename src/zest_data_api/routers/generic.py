"""Factory + registry that generate uniform CRUD routers for the diagram entities.

Each entity shares the same list/get/create/update/delete shape, so we build one
APIRouter per entity from its SQLAlchemy model, deriving request/response schemas
by reflection (see schemas/common.py).

NOTE: this module deliberately does NOT use ``from __future__ import annotations``.
FastAPI must see the dynamically-built request models and path-param types as real
objects (not stringized forward refs) to generate their OpenAPI schemas.
"""

from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from .. import crud
from ..db import get_db
from ..models import (
    BioreactorEquipmentSetup,
    DownstreamRelevance,
    Feedstock,
    FeedstockComposition,
    FeedstockFungiCombination,
    FermentationProcessRun,
    FungalSpeciesStrain,
    InoculumPreparation,
    MediaRecipe,
    MediaRecipeComponent,
    ProcessBiomassOutcome,
    ProcessObservation,
)
from ..schemas.common import (
    Page,
    build_create_model,
    build_read_model,
    build_update_model,
)


@dataclass
class CRUDEntity:
    prefix: str
    model: type
    tag: str
    key_field: str  # natural key used for /{key} routes ("id" for pure child tables)
    key_is_int: bool = False
    filter_fields: tuple[str, ...] = field(default_factory=tuple)


# One entry per diagram entity. raw_file / synthetic_run_spec / measurements are
# handled by dedicated routers, not here.
ENTITIES: list[CRUDEntity] = [
    CRUDEntity("/feedstocks", Feedstock, "feedstock", "feedstock_id"),
    CRUDEntity(
        "/feedstock-compositions", FeedstockComposition, "feedstock", "id",
        key_is_int=True, filter_fields=("feedstock_id",),
    ),
    CRUDEntity("/fungal-strains", FungalSpeciesStrain, "fungi", "fungi_id"),
    CRUDEntity(
        "/inoculum-preparations", InoculumPreparation, "fungi", "inoculum_id",
        filter_fields=("fungi_id",),
    ),
    CRUDEntity("/media-recipes", MediaRecipe, "media", "media_recipe_id"),
    CRUDEntity(
        "/media-recipe-components", MediaRecipeComponent, "media", "id",
        key_is_int=True, filter_fields=("media_recipe_id",),
    ),
    CRUDEntity("/equipment-setups", BioreactorEquipmentSetup, "equipment", "equipment_setup_id"),
    CRUDEntity(
        "/combinations", FeedstockFungiCombination, "core", "combination_id",
        filter_fields=("feedstock_id", "fungi_id", "media_recipe_id"),
    ),
    CRUDEntity(
        "/runs", FermentationProcessRun, "runs", "run_id",
        filter_fields=("combination_id", "equipment_setup_id", "is_synthetic"),
    ),
    CRUDEntity(
        "/biomass-outcomes", ProcessBiomassOutcome, "results", "outcome_id",
        filter_fields=("run_id",),
    ),
    CRUDEntity(
        "/observations", ProcessObservation, "results", "observation_id",
        filter_fields=("run_id",),
    ),
    CRUDEntity(
        "/downstream-relevances", DownstreamRelevance, "results", "cascading_id",
        filter_fields=("outcome_id",),
    ),
]


def _coerce(value: str) -> object:
    """Best-effort coercion of a query-string filter value."""
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    return value


def make_crud_router(entity: CRUDEntity) -> APIRouter:
    model = entity.model
    name = model.__name__
    ReadModel = build_read_model(model, f"{name}Read")
    CreateModel = build_create_model(model, f"{name}Create")
    UpdateModel = build_update_model(model, f"{name}Update", entity.key_field)

    router = APIRouter(prefix=entity.prefix, tags=[entity.tag])
    key_type = int if entity.key_is_int else str
    filter_doc = (
        f" Filterable query params: {', '.join(entity.filter_fields)}."
        if entity.filter_fields
        else ""
    )

    @router.get("", response_model=Page[ReadModel], summary=f"List {name}")
    def list_items(
        request: Request,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
    ):
        filters = {
            f: _coerce(request.query_params[f])
            for f in entity.filter_fields
            if f in request.query_params
        }
        rows, total = crud.list_rows(db, model, limit=limit, offset=offset, filters=filters)
        return Page[ReadModel](
            items=[ReadModel.model_validate(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    list_items.__doc__ = f"List {name} rows (paginated).{filter_doc}"

    @router.post("", response_model=ReadModel, status_code=201, summary=f"Create {name}")
    def create_item(payload: CreateModel, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        obj = crud.create_row(
            db, model, payload.model_dump(exclude_unset=True), key_field=entity.key_field
        )
        return ReadModel.model_validate(obj)

    @router.get("/{key}", response_model=ReadModel, summary=f"Get one {name}")
    def get_item(key: key_type, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        return ReadModel.model_validate(crud.get_row(db, model, entity.key_field, key))

    @router.patch("/{key}", response_model=ReadModel, summary=f"Update {name}")
    def update_item(key: key_type, payload: UpdateModel, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        obj = crud.update_row(
            db, model, entity.key_field, key, payload.model_dump(exclude_unset=True)
        )
        return ReadModel.model_validate(obj)

    @router.delete("/{key}", status_code=200, summary=f"Delete {name}")
    def delete_item(key: key_type, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        crud.delete_row(db, model, entity.key_field, key)
        return {"deleted": key}

    return router


def all_crud_routers() -> list[APIRouter]:
    return [make_crud_router(e) for e in ENTITIES]
