#!/usr/bin/env python3
"""Check deployment versions in the app and all embedded Mach-O binaries."""
import argparse
from pathlib import Path
import plistlib
import re
import subprocess

from verify_ipa import validate_info


def minimum_versions(output: str) -> list[str]:
    versions = re.findall(r"\bminos\s+(\d+(?:\.\d+)+)", output)
    if not versions:
        versions = re.findall(r"cmd LC_VERSION_MIN_IPHONEOS\s+cmdsize \d+\s+version (\d+(?:\.\d+)+)", output)
    return versions


def verify(app: Path, variant: str = "ipad16") -> None:
    validate_info(plistlib.loads((app / "Info.plist").read_bytes()), variant)
    limit = (16, 0, 0) if variant == "ipad16" else (18, 0, 0)
    # Read headers rather than relying on the app's MinimumOSVersion alone.
    magic = {bytes.fromhex(h) for h in ("feedface", "feedfacf", "cefaedfe", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca")}
    checked = 0
    for path in app.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as file:
            if file.read(4) not in magic:
                continue
        output = subprocess.run(["xcrun", "vtool", "-show-build", str(path)], check=True, capture_output=True, text=True).stdout
        versions = minimum_versions(output)
        if not versions:
            raise ValueError(f"Cannot determine deployment target of {path}")
        if any(tuple(map(int, v.split('.'))) > limit for v in versions):
            raise ValueError(f"{path} requires a newer OS: {versions}")
        checked += 1
    if not checked:
        raise ValueError("No Mach-O binaries found")
    print(f"Checked minimum OS versions of {checked} binaries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--variant", choices=["ipad16", "iphone"], default="ipad16")
    args = parser.parse_args()
    verify(args.app, args.variant)
