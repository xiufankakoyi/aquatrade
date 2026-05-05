# Core

Domain logic for AquaTrade. Code here should be reusable outside the web server.

- `backtest/`: backtest engines and execution helpers.
- `strategies/`: strategy implementations, templates, DSL, configurable strategies, and user strategies.
- `factors/`: reusable factor calculations.
- `portfolio/`: positions, watchlists, reporting, and portfolio signal logic.
- `similarity/`: K-line and pattern similarity logic.
- `feishu_bot/`: Feishu bot integration.
- `utils/`: shared utilities for core and server code.

Avoid adding HTTP route handlers, request parsing, local data dumps, or one-off experiments here.
