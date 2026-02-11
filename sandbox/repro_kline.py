import sys
import os
import pandas as pd

# Add current directory to path
sys.path.append(os.getcwd())

from server.visualization_api import BacktestVisualizationAPI
from config.config import Config

# Mock initialization if needed
api = BacktestVisualizationAPI()

# Try to get K-line data
symbol = '002449'
start = '2024-01-01'
end = '2024-02-01'

try:
    print(f"Fetching K-line for {symbol} from {start} to {end}...")
    kline = api.get_symbol_kline(symbol, start, end)
    print(f"Success! Got {len(kline)} records.")
    if len(kline) > 0:
        print("First record:", kline[0])
    else:
        print("Empty results returned.")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
