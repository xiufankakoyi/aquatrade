# Module map

Use this file as the first stop when looking for a module.

## Runtime entry points

- `run.py`: local application entry point.
- `server/asgi_entry.py`: ASGI application entry for Granian/production-like serving.
- `Procfile`: process definitions for Honcho.
- `ecosystem.config.js`: PM2 process definitions.
- `scripts/start/`: local launch scripts for LanceDB, no-docker, production, mock, and DragonEye modes.

## Main application layers

- `myapp/`: Vue frontend application.
- `server/`: HTTP/API layer, ASGI/Flask adapters, routes, services, background tasks, and server-side utilities.
- `core/`: domain logic that should not depend on web framework details.
- `data_svc/`: data ingestion, storage, loading, query, and data update services.
- `config/`: configuration modules and templates.

## Domain modules

- `core/backtest/`: backtest engines, matrix execution, and memory-efficient execution.
- `core/strategies/`: strategy implementations, DSL, configurable strategies, templates, and strategy utilities.
- `core/factors/`: reusable factor calculations.
- `core/portfolio/`: portfolio positions, watchlists, reporting, and portfolio signals.
- `core/similarity/`: K-line or pattern similarity matching.
- `core/feishu_bot/`: Feishu bot integration.
- `core/utils/`: shared Python utilities used by core/server code.

## Data modules

- `data_svc/storage/`: persistent storage adapters, LanceDB readers/managers, integrity checks, and unified readers/updaters.
- `data_svc/database/`: legacy and experimental database loaders/query helpers. Prefer `storage/` for new storage-facing code.
- `data_svc/ingestion/`: crawlers, gap checks, watermarking, and ingestion pipelines.
- `data_svc/analytics/`: analytics helpers over data frames or data service outputs.
- `data_svc/bridge/`: Arrow or cross-library bridge code.
- `data_svc/store/`: provider abstraction layer.

## API modules

- `server/routes/`: primary API route modules.
- `server/services/`: application services used by routes.
- `server/tasks/`: backend task code.
- `server/utils/`: server-only utility code.
- `server/routers/`: legacy/alternate router code. Prefer `server/routes/` for new routes unless migrating existing code.

## Tests and scratch work

- `test/`: maintained tests and fixtures.
- `myapp/e2e/`: frontend E2E specs.
- `sandbox/`: scratch investigations, one-off scripts, generated analysis, and temporary reproductions.
- `sandbox/root-scripts/`: scripts moved out of the repository root because they are one-off helpers.

## Local data and generated output

- `data/`: local market/runtime data. Do not import application code from here.
- `cache/`: generated cache.
- `quant/`: quant data snapshots and research artifacts. Move reusable logic into `core/` or `data_svc/`.
- `spider/`: crawler datasets/artifacts. Move reusable ingestion logic into `data_svc/ingestion/`.
- `.trae/`: local assistant/IDE state.

## Placement rules

- New backend endpoint: `server/routes/` plus business logic in `server/services/` or `core/`.
- New strategy: `core/strategies/`.
- New factor: `core/factors/`.
- New portfolio logic: `core/portfolio/`.
- New data reader/updater: `data_svc/storage/` or `data_svc/ingestion/`.
- New temporary diagnosis: `sandbox/`.
- New durable script: `scripts/`.
