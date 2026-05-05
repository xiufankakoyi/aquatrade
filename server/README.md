# Server

Backend application layer.

- `asgi_entry.py`: ASGI application entry.
- `routes/`: primary API route modules.
- `services/`: application services used by route modules.
- `tasks/`: background task helpers.
- `utils/`: server-only utilities.
- `routers/`: legacy or alternate router modules. Prefer `routes/` for new endpoint modules.

Keep framework-specific request/response code here. Put reusable trading/data logic in `core/` or `data_svc/`.
