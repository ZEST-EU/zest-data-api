# zest-data-api

A FastAPI + SQLAlchemy service for the ZEST platform's **experimental fermentation datasets**. It has
two concerns:

1. **Datasets** — upload one or more files as a named dataset. The **file bytes are stored in MinIO**
   (S3-compatible object storage); **Postgres holds the metadata** (`dataset` / `dataset_file`). A
   generic multi-file upload API backs the [`zest-dashboard`](../zest-dashboard) "Datasets" tab.
2. **Structured data** — the ZEST relational model from `zest_diagram.pdf` (feedstock, fungi, media,
   runs, outcomes, …) with uniform CRUD, available via the API for structured data entry.

Both use the standalone `postgres-db` + `minio` deployed by
[`zest-cloud-k8s`](../zest-cloud-k8s/k8s) — a store **separate** from the FIWARE
Orion → QuantumLeap → CrateDB time-series pipeline.

- **Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2 (ORM), Alembic, psycopg v3, Pydantic v2, MinIO SDK.
- **Layout:** `src/` package; portable models (schema also runs on SQLite) + an in-memory object store,
  so the test suite and a bare `uvicorn` need **no external services**.

## Quick start (local dev)

```bash
uv sync --extra dev                       # create .venv, install deps
cp .env.example .env                      # defaults: DB :5433, MinIO :9000

docker compose up -d db minio             # Postgres 16 (:5433) + MinIO (:9000 API, :9001 console)
uv run alembic upgrade head               # create the schema
uv run uvicorn zest_data_api.main:app --reload --port 8091

# upload the example data-temp/ files as one dataset (stdlib-only script)
python3 scripts/upload_dataset.py ../data-temp --name SIM-01
```

Interactive API docs: <http://localhost:8091/docs>. MinIO console:
<http://localhost:9001> (`zest` / `zest-minio-dev`). The app auto-creates the `datasets` bucket on
startup.

> Leave `ZEST_API_STORAGE_ENDPOINT` empty to use the **in-memory** object store (no MinIO needed) —
> handy for a quick look or for tests.

## Configuration

All settings are environment variables prefixed `ZEST_API_` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `ZEST_API_DATABASE_URL` | `postgresql+psycopg://zest:zest@localhost:5433/zest` | SQLAlchemy URL (psycopg v3) |
| `ZEST_API_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins (JSON or CSV) |
| `ZEST_API_ROOT_PATH` | `` | Root path behind a stripping proxy |
| `ZEST_API_MAX_UPLOAD_BYTES` | `67108864` | Per-file upload cap |
| `ZEST_API_STORAGE_ENDPOINT` | `` (→ in-memory) | MinIO endpoint, e.g. `localhost:9000` / `minio:9000` |
| `ZEST_API_STORAGE_ACCESS_KEY` | `zest` | MinIO access key |
| `ZEST_API_STORAGE_SECRET_KEY` | `zest-minio-dev` | MinIO secret key |
| `ZEST_API_STORAGE_BUCKET` | `datasets` | Bucket for dataset objects |
| `ZEST_API_STORAGE_SECURE` | `false` | Use TLS to MinIO |

## Data model

**Datasets (object storage).** `src/zest_data_api/models/datasets.py` — `dataset` (surrogate `id`,
unique `dataset_id` slug `ds_<hex>`, `name`, `description`, timestamps) 1:N `dataset_file`
(`filename`, `object_key`, `content_type`, `size_bytes`, `etag`). The bytes live in MinIO at
`<dataset_id>/<filename>`; the abstraction (`src/zest_data_api/storage.py`) has a `MinioStore` and an
in-memory `MemoryStore`, chosen by `ZEST_API_STORAGE_ENDPOINT`.

**Structured schema (Postgres).** `models/reference.py`, `core.py`, `results.py` implement the 12
diagram entities with surrogate `BIGINT` PKs + unique natural keys + real FK constraints, typed
`value_num`/`unit`, enum-with-CHECK categorical fields, and a normalized `media_recipe` +
`media_recipe_component`. These are exposed via generic CRUD (below).

Migrations (`migrations/versions/`): the baseline created the full diagram schema; a follow-up moved
dataset files to object storage — dropping `raw_file`, `process_measurement_record`,
`synthetic_run_spec` and adding `dataset` / `dataset_file`.

## API

Browse <http://localhost:8091/docs>. Highlights:

**Datasets** (a dataset = a named bundle of files in MinIO)
- `POST /datasets` — **multipart, generic**: one or more `files` + optional `name`, `description`.
  Stores each file in MinIO and records metadata. Returns the dataset detail.
- `GET /datasets` — paginated catalogue (per-dataset `file_count` + `total_size`).
- `GET /datasets/{dataset_id}` — detail with the file list.
- `GET /datasets/{dataset_id}/download` — zip of all files (streamed from MinIO).
- `GET /datasets/{dataset_id}/files/{file_id}` — one file (streamed from MinIO).
- `DELETE /datasets/{dataset_id}` — remove the objects (MinIO) and the metadata (cascade).

**CRUD** — uniform list/get/create/update/delete for every diagram entity, e.g. `/feedstocks`,
`/fungal-strains`, `/media-recipes`, `/equipment-setups`, `/combinations`, `/runs`,
`/biomass-outcomes`, `/observations`, `/downstream-relevances`. Child tables accept filters
(e.g. `GET /feedstock-compositions?feedstock_id=FS-1`). Errors use the
`{"error":{code,message,detail}}` contract shared with `zest-model-service`.

## Tests

```bash
uv run pytest            # in-memory SQLite + in-memory object store — no services needed
uv run ruff check src tests scripts
```

## Deploy to zest-cloud-k8s

Manifests: `../zest-cloud-k8s/k8s/zest-data-api/` (`ClusterIP` on `:8091`, an `alembic upgrade head`
initContainer, `/health` probes, and `ZEST_API_STORAGE_*` env pointing at the in-cluster `minio`
service) plus `../zest-cloud-k8s/k8s/minio/` (MinIO deployment + service + PVC). The image is built +
pushed by this repo's CI (`.github/workflows/docker-publish.yml`) → `ghcr.io/zest-eu/zest-data-api`.

```bash
# 1. publish the image: push to ZEST-EU/zest-data-api on GitHub + tag a release (CI → GHCR)
# 2. apply (postgres-db + minio must be up; add a ghcr-pull secret if the package is private):
kubectl apply -f ../zest-cloud-k8s/k8s/postgres/
kubectl apply -f ../zest-cloud-k8s/k8s/minio/
kubectl apply -f ../zest-cloud-k8s/k8s/zest-data-api/
kubectl rollout status deploy/zest-data-api
# 3. verify:
kubectl port-forward svc/zest-data-api 8091:8091   # curl localhost:8091/health
```

For **local minikube**: `minikube image load ghcr.io/zest-eu/zest-data-api:local` and set
`imagePullPolicy: Never` on both containers.

## Dashboard integration (done)

`zest-dashboard` has a **Datasets** tab (standard multi-file upload + a list of MinIO-backed datasets
with downloads), alongside its existing Orion/QuantumLeap live feed (untouched). It reaches the API
same-origin at `/api/data` (Vite dev proxy + nginx prod). Client: `src/api/datasets.js`; page:
`src/components/DatasetsPage.jsx`. Run the dashboard with **Node 20** (`nvm use`).
