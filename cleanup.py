#!/usr/bin/env python
"""Quick cleanup before starting service"""
import subprocess, sys, time
for exe in ["python.exe", "node.exe"]:
    subprocess.run(["taskkill", "/F", "/IM", exe, "/T"], capture_output=True)
time.sleep(0.5)
