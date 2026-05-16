import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

spider_path = Path(r'c:\Users\Liu\Desktop\projects\aquatrade\data_svc\spiders\dragon_spider\main.py')

dates = ['2026-03-10', '2026-03-11', '2026-03-12']

for target_date in dates:
    print(f'\n=== Processing {target_date} ===')
    cmd = [sys.executable, str(spider_path), '--date', target_date]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(spider_path.parent),
        encoding='utf-8',
        errors='replace',
    )
    
    print(f'Return code: {result.returncode}')
    if result.returncode != 0:
        print(f'Stderr: {result.stderr[:300]}')