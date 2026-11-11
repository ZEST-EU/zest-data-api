# zest-data-api

A FastAPI + SQLAlchemy service for storing and serving **ZEST fungal-fermentation experimental
datasets** in PostgreSQL. It implements the ZEST core data model (`zest_diagram.pdf`), ingests runs
produced by the sibling [`zest-model-service`](../zest-model-service) (the `SIM-01`
`*_log.csv` / `*_labels.csv` / `*_truth.json` format), and exposes a REST API for browsing,
querying, and downloading datasets — to be consumed by [`zest-dashboard`](../zest-dashboard).

The database it targets is the standalone `postgres-db` deployed by
[`zest-cloud-k8s`](../zest-cloud-k8s/k8s/postgres) — a relational store **separate** from the FIWARE
Orion → QuantumLeap → CrateDB time-series pipeline.

- **Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2 (ORM), Alembic, psycopg v3, Pydantic v2.
- **Layout:** `src/` package, portable models (full schema also runs on SQLite for tests).

## Quick start (local dev)

```bash
uv sync --extra dev                       # create .venv, install deps
cp .env.example .env                      # defaults point at the compose DB on :5433

docker compose up -d db                   # Postgres 16 (zest/zest/zest) on host port 5433
uv run alembic upgrade head               # create the schema
uv run uvicorn zest_data_api.main:app --reload --port 8091

# ingest the example dataset through the API (stdlib-only script)
python3 scripts/upload_dataset.py ../data-temp --api-url http://localhost:8091
```

Interactive API docs: <http://localhost:8091/docs>.

> The dev DB is published on **5433** to avoid clashing with a native Postgres on 5432. To use the
> real cluster DB instead, `kubectl port-forward svc/postgres-db 5432:5432` and point
> `ZEST_API_DATABASE_URL` at `...@localhost:5432/zest`.

## Configuration

All settings are environment variables prefixed `ZEST_API_` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `ZEST_API_DATABASE_URL` | `postgresql+psycopg://zest:zest@localhost:5433/zest` | SQLAlchemy URL (psycopg v3) |
| `ZEST_API_DB_ECHO` | `false` | Log SQL |
| `ZEST_API_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins (JSON or CSV) |
| `ZEST_API_ROOT_PATH` | `` | Root path behind a stripping proxy (e.g. `/api/datasets`) |
| `ZEST_API_MAX_UPLOAD_BYTES` | `67108864` | Per-file upload cap |

## Data model

SQLAlchemy models live in `src/zest_data_api/models/` (`reference.py`, `core.py`, `results.py`),
mirroring the three bands of the diagram. All 12 diagram entities are implemented, **plus two
storage additions**. The baseline migration is `migrations/versions/*_baseline_schema.py`.

**Reference / inputs** — `feedstock` + `feedstock_composition`, `fungal_species_strain` +
`inoculum_preparation`, `media_recipe` + `media_recipe_component`, `bioreactor_equipment_setup`.
**Core** — `feedstock_fungi_combination`, `fermentation_process_run`, `process_measurement_record`
(long/EAV time series). **Results** — `process_biomass_outcome`, `process_observation`,
`downstream_relevance`.

### Changes made vs. the proposed diagram

- **Surrogate `BIGINT` PKs + unique natural keys + real FKs.** Every table has an internal `id` and
  keeps its business key (`run_id`, `feedstock_id`, …) as a unique column; FKs reference those
  natural keys, so links match the diagram while staying rename-safe.
- **Typed values.** `value + unit` → numeric `value_num` (+ `value_text`) and a separate `unit`;
  timepoints are numeric `time_h` (with an optional absolute `timepoint`).
- **Normalized media recipe.** The diagram repeats the recipe id per component; split into a
  `media_recipe` header + `media_recipe_component` children.
- **`raw_file` (addition).** Stores each uploaded file verbatim (BYTEA + sha256) so downloads are
  byte-exact — EAV melting is lossy w.r.t. float formatting and column order.
- **`synthetic_run_spec` (addition).** Holds `truth.json`'s `spec` + `kinetics` as JSONB (no home in
  the diagram); plus `is_synthetic` / `generator` / `seed` on the run.
- **`is_ground_truth` flag** on measurements separates the `truth_*` channels from observed data.
- Small fixes: `rotation_spood_range` → `rotation_speed_range`; nullable `combination_id` /
  `equipment_setup_id` on runs (synthetic runs have neither). A handful of categorical fields
  (`process_mode`, `process_status`, `run_scale`, `value_status`, `severity`) are enums with CHECK
  constraints; everything else stays free-text, including the optional ChEBI/QUDT/NCBI/FoodOn/FIWARE
  mapping columns.

## API

Browse <http://localhost:8091/docs> for the full, typed surface. Highlights:

**Datasets** (a dataset = a run + its raw files)
- `POST /datasets` — multipart upload (`log`, optional `labels`, optional `truth`; `?replace=true`).
  Melts the log into measurements, stores spec/kinetics, keeps raw files. Idempotent per `run_id`.
- `GET /datasets` — catalogue (counts, duration, synthetic flag). `?is_synthetic=`.
- `GET /datasets/{run_id}` — detail: files, per-property summary, spec/kinetics.
- `GET /datasets/{run_id}/download` — zip of the original files.
- `GET /datasets/{run_id}/files/{kind}` — one original file (`log` | `labels` | `truth`).

**Measurements**
- `GET /runs/{run_id}/measurements` — filter by `property`, `is_ground_truth`, `from_h`, `to_h`
  (paginated) — the series endpoint for dashboard charts.
- `GET /runs/{run_id}/measurements.csv` — re-pivoted wide CSV (`?include_ground_truth=`).

**CRUD** — uniform list/get/create/update/delete for every diagram entity, e.g. `/feedstocks`,
`/fungal-strains`, `/media-recipes`, `/equipment-setups`, `/combinations`, `/runs`,
`/biomass-outcomes`, `/observations`, `/downstream-relevances`. Child tables accept filters
(e.g. `GET /feedstock-compositions?feedstock_id=FS-1`). Errors use the
`{"error":{code,message,detail}}` contract shared with `zest-model-service`.

## Tests

```bash
uv run pytest            # in-memory SQLite — no services needed (FK enforcement on)
uv run ruff check src tests scripts
```

## Deploy to zest-cloud-k8s

Manifests live in `../zest-cloud-k8s/k8s/zest-data-api/` (`deployment.yaml` + `service.yaml`): a
`ClusterIP` Service on `:8091`, an initContainer that runs `alembic upgrade head` against
`postgres-db` before the API starts, and `/health` probes. The image build + push is handled by this
repo's CI (`.github/workflows/docker-publish.yml`) → `ghcr.io/zest-eu/zest-data-api`.

1. **Publish the image.** Push this repo to `ZEST-EU/zest-data-api` on GitHub and create a tag
   (`git push origin v0.1.0`, or draft a Release) — CI builds and pushes
   `ghcr.io/zest-eu/zest-data-api:latest`. (Locally the image builds and runs: `docker build -t
   ghcr.io/zest-eu/zest-data-api:local .` → serves `/health`, initContainer `alembic upgrade head`
   connects to Postgres.)
2. **If the GHCR package is private**, create a pull secret in the cluster and uncomment
   `imagePullSecrets` in `deployment.yaml`:
   ```bash
   kubectl create secret docker-registry ghcr-pull \
     --docker-server=ghcr.io --docker-username=<gh-user> --docker-password=<PAT-with-read:packages>
   ```
3. **Apply** (the cluster is the current kubectl context; `postgres-db` must be up):
   ```bash
   kubectl apply -f ../zest-cloud-k8s/k8s/postgres/        # if not already running
   kubectl apply -f ../zest-cloud-k8s/k8s/zest-data-api/
   kubectl rollout status deploy/zest-data-api
   ```
4. **Verify**: `kubectl port-forward svc/zest-data-api 8091:8091`, then `curl localhost:8091/health`
   and upload a dataset with `scripts/upload_dataset.py`.

For a **local minikube** cluster instead of a registry: `minikube image load
ghcr.io/zest-eu/zest-data-api:local` and set `imagePullPolicy: Never` on both containers.

## Dashboard integration (done)

`zest-dashboard` now has a **Datasets** tab (upload + browse + download) wired to this API, alongside
its existing Orion/QuantumLeap live feed (untouched). It reaches the API same-origin at `/api/data`
via the dashboard's Vite dev proxy and nginx prod config (`VITE_DATA_API_URL` / `DATA_API_URL`,
default `http://localhost:8091` / `http://zest-data-api:8091`). Client: `src/api/datasets.js`;
page: `src/components/DatasetsPage.jsx`.

Run both locally (the dashboard needs **Node 20** — see its `.nvmrc`):

```bash
# terminal 1 — this API
uv run uvicorn zest_data_api.main:app --port 8091
# terminal 2 — the dashboard
cd ../zest-dashboard && nvm use && npm run dev     # http://localhost:5173 -> "Datasets" tab
```
