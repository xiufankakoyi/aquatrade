#!/usr/bin/env python
"""Generate local data health reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.data_health_service import build_data_health_report


if __name__ == "__main__":
    result = build_data_health_report(write_files=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
