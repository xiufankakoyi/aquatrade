# Quant Subproject

Standalone quant research and market briefing subproject.

This directory is not part of the main backend module layout. When code here becomes reusable by the app, migrate it into:

- `core/` for strategy, factor, portfolio, or analysis logic.
- `data_svc/` for ingestion, data loading, update, or storage logic.
- `scripts/` for durable operational scripts.

Runtime data and generated reports should stay ignored.
