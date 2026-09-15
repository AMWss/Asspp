#!/usr/bin/env python3
"""Regenerate the runtime-only compatibility patch against the recorded upstream base."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
base = (root / "Resources/Patches/ios16-base.txt").read_text().strip()
paths = ["Asspp", "Configuration", "Asspp.xcodeproj"]
untracked = subprocess.check_output(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "--", *paths])
if untracked:
    raise SystemExit("Stage new runtime files before regenerating the compatibility patch.")
patch = subprocess.check_output(["git", "-C", str(root), "-c", "core.autocrlf=true", "-c", "core.safecrlf=false", "diff", "--binary", base, "--", *paths])
if not patch:
    raise SystemExit("No compatibility changes found")
(root / "Resources/Patches/ios16.patch").write_bytes(patch)
print("Updated Resources/Patches/ios16.patch")
