import subprocess
import sys
from pathlib import Path

spider_path = Path(r'c:\Users\Liu\Desktop\projects\aquatrade\data_svc\spiders\dragon_spider\main.py')
target_date = '2026-04-08'

cmd = [sys.executable, str(spider_path), '--date', target_date]
print(f'Running: {" ".join(cmd)}')
print(f'CWD: {spider_path.parent}')
print()

result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=300,
    cwd=str(spider_path.parent),
    encoding='utf-8',
    errors='replace',
)

print(f'Return code: {result.returncode}')
print(f'Stdout:\n{result.stdout}')
if result.stderr:
    print(f'Stderr:\n{result.stderr}')