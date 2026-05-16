# API Documentation

## Automatic API Docs (Swagger UI)
The backend provides automatic API documentation using Swagger UI.

- **URL**: `http://localhost:8000/apidocs` (or whatever port the server runs on)
- **Spec**: `http://localhost:8000/apispec_1.json`

## REST API
### Strategies
- `GET /api/strategies`: List all available strategies
- `GET /api/strategies/<id>/params`: Get parameters for a strategy

### Data
- `GET /api/kline`: Get K-line data
- `GET /api/latest_price`: Get current prices

### Industry Chain Radar
- `GET /api/industry-chain/chains`: List local industry chain definitions from `knowledge/industry_chains`.
- `GET /api/industry-chain/graph?chain_id=optical_communication`: Return ECharts graph data with nodes, edges, layers, and summary.
- `GET /api/industry-chain/node/<node_id>?chain_id=optical_communication`: Return node detail, upstream/downstream nodes, metrics, and mapped stocks.
- `GET /api/industry-chain/node/<node_id>/stocks?chain_id=optical_communication`: Return verified local mappings and optional external candidates. Empty data is valid and should render an empty state.
- `GET /api/industry-chain/debug`: Return diagnostic paths and counts including `project_root`, `knowledge_path`, `industry_chain_files`, `loaded_chains`, `optical_communication_exists`, `node_count`, `edge_count`, and `stock_mapping_count`.

## Socket.IO Events
- `connect`: Client connection
- `start_backtest`: Trigger a backtest
- `backtest_update`: Real-time backtest progress
