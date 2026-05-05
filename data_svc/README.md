# Data Service

Data ingestion, storage, query, and update layer.

- `storage/`: persistent storage adapters, LanceDB readers/managers, integrity checks, and unified readers/updaters.
- `database/`: legacy and experimental database loaders/query helpers. Prefer `storage/` for new storage-facing code.
- `ingestion/`: crawlers, gap checks, watermarking, and ingestion pipelines.
- `analytics/`: analytics helpers over data frames or data service outputs.
- `bridge/`: Arrow and cross-library bridge code.
- `store/`: provider abstraction layer.

Do not put route handlers or frontend-specific logic here.
