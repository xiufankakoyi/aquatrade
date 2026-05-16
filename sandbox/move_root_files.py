import os
import shutil
from pathlib import Path

root = Path(r"c:\Users\Liu\Desktop\projects\aquatrade")
sandbox = root / "sandbox"

patterns = [
    "check_*.py",
    "debug_*.py",
    "test_*.py",
    "diagnose_*.py",
    "final_*.py",
    "fast_*.py",
    "quick_*.py",
    "optimize_*.py",
    "compare_*.py",
    "fill_*.py",
    "fix_*.py",
    "import_*.py",
    "insert_*.py",
    "list_*.py",
    "continuous_*.py",
    "create_*.py",
    "enable_*.py",
    "kelly_*.py",
    "ml_*.py",
    "profile_*.py",
    "repro_*.py",
    "restore_*.py",
    "add_*.py",
    "clear_*.py",
    "delete_*.py",
    "restart_*.py",
    "reload_*.py",
    "recompute_*.py",
    "recreate_*.py",
    "analyze_*.py",
    "inspect_*.py",
    "start_*.bat",
    "run_*.py",
]

keep_in_root = {
    "README.md", "STARTUP.md", "package.json", "Procfile",
    ".env.template", ".honcho", "requirements.txt",
    "docker-compose.yml", "pytest.ini", "ecosystem.config.js",
    "start.bat", "start_aquatrade.bat",
    "run.py", "worker.py", "add_positions.py",
    "start_dragon_server.py", "setup_qdb_views.py",
}

moved_count = 0
skipped_count = 0

for pattern in patterns:
    for f in root.glob(pattern):
        if f.name in keep_in_root:
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
