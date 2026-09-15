#!/usr/bin/env python3
"""Validate the exported iPadOS 16 IPA before publishing an install link."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import plistlib
import subprocess
import tempfile
import zipfile


def validate_info(info: dict, variant: str = "ipad16") -> None:
    version = tuple(int(n) for n in info["MinimumOSVersion"].split("."))
    limit = (16, 0, 0) if variant == "ipad16" else (18, 0, 0)
    if version > limit:
        raise ValueError(f"IPA requires iOS {info['MinimumOSVersion']}, expected <= {limit[0]}.0")
    if variant == "ipad16" and info.get("UIDeviceFamily") != [2]:
        raise ValueError("Expected an iPad-only app (UIDeviceFamily = [2])")
    if variant == "iphone" and 1 not in info.get("UIDeviceFamily", []):
        raise ValueError("The iPhone OTA cannot publish an iPad-only app")
    for key in ("CFBundleIdentifier", "CFBundleVersion", "CFBundleShortVersionString"):
        if not info.get(key):
            raise ValueError(f"Missing {key}")


def validate_profile(profile: dict, info: dict) -> None:
    expiry = profile["ExpirationDate"].replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("Provisioning profile has expired")
    entitlements = profile["Entitlements"]
    if entitlements.get("get-task-allow", False):
        raise ValueError("OTA publishing requires a distribution profile, not a development profile")
    if not profile.get("ProvisionedDevices") and not profile.get("ProvisionsAllDevices"):
        raise ValueError("App Store profiles cannot be installed through this OTA page")
    app_id = entitlements["application-identifier"]
    prefix, pattern = app_id.split(".", 1)
    bundle_id = info["CFBundleIdentifier"]
    matches = bundle_id.startswith(pattern[:-1]) if pattern.endswith("*") else bundle_id == pattern
    if not matches or prefix not in profile["ApplicationIdentifierPrefix"]:
        raise ValueError("Provisioning profile does not match the app identifier")


def verify(path: Path, signed: bool, variant: str = "ipad16") -> dict:
    with zipfile.ZipFile(path) as ipa:
        apps = [n for n in ipa.namelist() if n.startswith("Payload/") and n.endswith(".app/Info.plist") and n.count("/") == 2]
        if len(apps) != 1:
            raise ValueError("Expected exactly one app in Payload")
        info = plistlib.loads(ipa.read(apps[0]))
        validate_info(info, variant)
        if signed:
            profile_path = apps[0].removesuffix("Info.plist") + "embedded.mobileprovision"
            with tempfile.TemporaryDirectory() as directory:
                profile_file = Path(directory) / "embedded.mobileprovision"
                profile_file.write_bytes(ipa.read(profile_path))
                result = subprocess.run(["security", "cms", "-D", "-i", str(profile_file)], check=True, capture_output=True)
                validate_profile(plistlib.loads(result.stdout), info)
        return info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--signed", action="store_true")
    parser.add_argument("--variant", choices=["ipad16", "iphone"], default="ipad16")
    args = parser.parse_args()
    info = verify(args.ipa, args.signed, args.variant)
    print(f"Validated {args.variant}: {info['CFBundleIdentifier']} build {info['CFBundleVersion']}, iOS {info['MinimumOSVersion']}+")
