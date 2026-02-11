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

## Socket.IO Events
- `connect`: Client connection
- `start_backtest`: Trigger a backtest
- `backtest_update`: Real-time backtest progress
