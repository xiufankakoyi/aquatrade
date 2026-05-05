# Project structure

This repository keeps durable source files separate from generated runtime files.

## Source directories

- `server/`: backend API entry points, routes, services, and tasks.
- `core/`: trading, strategy, portfolio, similarity, and shared domain logic.
- `data_svc/`: data ingestion, storage, query, and data service adapters.
- `myapp/`: frontend application.
- `config/`: non-secret configuration templates and defaults.
- `scripts/`: maintained operational scripts.
- `scripts/start/`: launchers for local backend, frontend, and data-service modes.
- `scripts/legacy/`: older entry points kept for reference or manual migration.
- `docs/`: durable project documentation.
- `test/`: maintained test fixtures and test suites.

## Working directories

- `data/`: local runtime data only. Large datasets, matrix caches, reports, and local secrets stay untracked.
- `cache/`: local generated cache only.
- `sandbox/`: one-off experiments, diagnostics, and scratch scripts. Do not duplicate production modules here.
- `update/`: update jobs and ad hoc update helpers.
- `profiles/`: local profiling output.

## Directory hygiene

- Keep frontend-only tests under `myapp/e2e/`; keep backend or cross-system tests under `test/`.
- Keep reusable operational scripts under `scripts/`; keep startup launchers under `scripts/start/`; keep temporary investigation scripts under `sandbox/`.
- Do not create root-level debug scripts or screenshots. Put temporary files under `sandbox/` or let the ignored report directories hold them.
- Do not commit dependency directories, virtual environments, browser reports, coverage output, matrix caches, or local data files.
- Use `docs/MODULE_MAP.md` when deciding where a new module belongs.
