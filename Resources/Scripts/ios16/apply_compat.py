#!/usr/bin/env python3
"""Apply the reviewed backport to a clean upstream checkout; stop on conflicts."""
import argparse
from pathlib import Path
import subprocess


def apply(source: Path, patch: Path) -> None:
    source, patch = source.resolve(), patch.resolve()
    # Do not reset, clean, or silently accept an already-patched/partial tree.
    subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)], check=True)
    subprocess.run(["git", "-C", str(source), "apply", str(patch)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    apply(args.source, Path(__file__).resolve().parents[2] / "Patches/ios16.patch")
