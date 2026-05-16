import os
import shutil
from pathlib import Path

root = Path(r"c:\Users\Liu\Desktop\projects\aquatrade")
sandbox = root / "sandbox"

patterns_to_move = [
    "*.png",
    "*.ps1",
    "*.txt",
    "*.js",
]

keep_in_root = {
    "README.md", "STARTUP.md", "package.json", "Procfile",
    ".env.template", ".honcho", "requirements.txt",
    "docker-compose.yml", "pytest.ini", "ecosystem.config.js",
    "start.bat", "start_aquatrade.bat",
    "run.py", "worker.py", "add_positions.py",
    "start_dragon_server.py", "setup_qdb_views.py",
    ".gitignore",
}

keep_patterns = [
    "requirements.txt",
    "docker-compose.yml",
    "ecosystem.config.js",
    "pytest.ini",
    ".honcho",
    "parquet_schema*.txt",
]

moved_count = 0
skipped_count = 0

for pattern in patterns_to_move:
    for f in root.glob(pattern):
        should_keep = False
        for keep in keep_in_root:
            if f.name == keep:
                should_keep = True
                break
        for keep in keep_patterns:
            if Path(keep).match(keep) and f.match(keep):
                should_keep = True
                break
        if should_keep:
            print(f"SKIP (keep in root): {f.name}")
            skipped_count += 1
            continue
        dest = sandbox / f.name
        if dest.exists():
            print(f"REPLACE (sandbox exists): {f.name}")
            dest.unlink()
        shutil.move(str(f), str(dest))
        print(f"MOVED: {f.name} -> sandbox/")
        moved_count += 1

print(f"\n=== Summary ===")
print(f"Moved: {moved_count} files")
print(f"Skipped: {skipped_count} files")
