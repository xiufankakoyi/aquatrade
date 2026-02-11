# Developer Guide

## Architecture
- **Backend**: Python (Flask + Granian + Socket.IO)
- **Frontend**: Vue.js (Vite)
- **Database**: QuestDB (Time-series), DuckDB (OLAP), LanceDB (Vector)

## Setup
1. Clone repository
2. Install Python 3.10+
3. `pip install -r requirements.txt`
4. Configure `.env` file

## Folder Structure
- `core/`: Core trading logic (Backtest engine, strategies)
- `server/`: API server and WebSocket handlers
- `data_svc/`: Data query services
- `docs/`: Documentation
