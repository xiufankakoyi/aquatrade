import subprocess
import sys
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'

result = subprocess.run(
    ['python', 'main.py', '--date', sys.argv[1] if len(sys.argv) > 1 else '2026-01-28'],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace',
    cwd='c:\\Users\\Liu\\Desktop\\projects\\quant'
)

sys.stdout.buffer.write(f"STDOUT: {result.stdout}\n".encode('utf-8'))
sys.stdout.buffer.write(f"STDERR: {result.stderr}\n".encode('utf-8'))
sys.stdout.buffer.write(f"Return code: {result.returncode}\n".encode('utf-8'))
