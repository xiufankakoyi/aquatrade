#!/usr/bin/env python3
"""
Import benchmark_daily.parquet to QuestDB
"""
import polars as pl
import sys
import socket
import time

sys.path.insert(0, r'd:\aquatrade')

from data_svc.database.questdb_manager import get_questdb_manager

def main():
    print('Reading benchmark_daily.parquet...')
    df = pl.read_parquet(r'd:\aquatrade\data\parquet_data\benchmark_daily.parquet')
    print(f'Loaded {len(df)} rows')
    print(f'Columns: {df.columns}')
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # Rename columns to match QuestDB schema
    df = df.rename({
        'date': 'timestamp',
        'code': 'stock_code'
    })

    print('\nConnecting to QuestDB...')
    qdb = get_questdb_manager()

    # Check connection
    try:
        result = qdb.query('SELECT 1')
        print(f'Connection test: {result}')
    except Exception as e:
        print(f'Connection failed: {e}')
        return 1

    # Check if table exists, if so drop it
    print('\nDropping existing table if exists...')
    try:
        qdb.query('DROP TABLE IF EXISTS benchmark_data')
        print('Dropped existing benchmark_data table')
    except Exception as e:
        print(f'Drop table result: {e}')

    # Create table
    print('\nCreating benchmark_data table...')
    create_sql = '''
    CREATE TABLE benchmark_data (
        timestamp TIMESTAMP,
        stock_code SYMBOL,
        close DOUBLE
    ) TIMESTAMP(timestamp) PARTITION BY YEAR
    '''
    try:
        result = qdb.query(create_sql)
        print('Table created successfully')
    except Exception as e:
        print(f'Error creating table: {e}')
        return 1

    # Insert data using ILP (InfluxDB Line Protocol)
    print('\nInserting data via ILP...')
    try:
        rows = df.to_dicts()
        ilp_lines = []
        for row in rows:
            ts = row['timestamp']
            code = row['stock_code']
            close = row['close']
            # Convert date string to nanoseconds timestamp
            ts_ns = int(time.mktime(time.strptime(ts, '%Y-%m-%d'))) * 1000000000
            # ILP format: table_name,symbols fields timestamp
            ilp_line = f'benchmark_data,stock_code={code} close={close} {ts_ns}'
            ilp_lines.append(ilp_line)

        # Send via socket to port 9009
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(('localhost', 9009))

        batch_size = 1000
        total = len(ilp_lines)
        for i in range(0, total, batch_size):
            batch = ilp_lines[i:i+batch_size]
            data = '\n'.join(batch) + '\n'
            sock.sendall(data.encode())
            if (i // batch_size) % 10 == 0:
                print(f'  Progress: {i}/{total} rows ({i/total*100:.1f}%)')

        sock.close()
        print(f'Successfully inserted {total} rows')

    except Exception as e:
        print(f'Error inserting data: {e}')
        import traceback
        traceback.print_exc()
        return 1

    # Wait a moment for data to be committed
    print('\nWaiting for data to be committed...')
    time.sleep(2)

    # Verify
    print('\nVerifying data...')
    try:
        result = qdb.query('SELECT count() FROM benchmark_data')
        print(f'Total rows in QuestDB: {result}')

        result = qdb.query('SELECT min(timestamp), max(timestamp) FROM benchmark_data')
        print(f'Date range: {result}')

        # Sample query
        result = qdb.query("SELECT * FROM benchmark_data LIMIT 5")
        print(f'Sample data:\n{result}')

        print('\nDone! benchmark_data table is ready.')
        return 0
    except Exception as e:
        print(f'Verification failed: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
