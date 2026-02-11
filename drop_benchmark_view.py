#!/usr/bin/env python3
import sys
sys.path.insert(0, r'd:\aquatrade')
from data_svc.database.questdb_manager import get_questdb_manager

qdb = get_questdb_manager()

# Try to drop as view
print('Trying to drop as view...')
try:
    result = qdb.query('DROP VIEW IF EXISTS benchmark_data')
    print(f'Drop view result: {result}')
except Exception as e:
    print(f'Drop view error: {e}')

# Try to drop as materialized view
print('\nTrying to drop as materialized view...')
try:
    result = qdb.query('DROP MATERIALIZED VIEW IF EXISTS benchmark_data')
    print(f'Drop materialized view result: {result}')
except Exception as e:
    print(f'Drop materialized view error: {e}')

# Try to drop as table
print('\nTrying to drop as table...')
try:
    result = qdb.query('DROP TABLE IF EXISTS benchmark_data')
    print(f'Drop table result: {result}')
except Exception as e:
    print(f'Drop table error: {e}')

# Check what exists
print('\nChecking tables...')
try:
    result = qdb.query("SHOW TABLES")
    print(f'Tables: {result}')
except Exception as e:
    print(f'Show tables error: {e}')
