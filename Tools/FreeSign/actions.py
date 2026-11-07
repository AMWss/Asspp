"""GitHub artifact transport, encrypted state, 2FA mailbox and IPA packaging."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        if urllib.parse.urlsplit(new_url).scheme != "https":
            raise ValueError("Downloads require HTTPS")
        redirected = super().redirect_request(request, fp, code, message, headers, new_url)
        if urllib.parse.urlsplit(request.full_url).netloc != urllib.parse.urlsplit(new_url).netloc:
            redirected.remove_header("Authorization")
        return redirected


def fetch(url, authenticated=False, limit=16 * 1024 * 1024):
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError("Downloads require HTTPS")
    headers = {"User-Agent": "Asspp-Free-Sign", "Accept": "application/vnd.github+json"}
    if authenticated:
        if urllib.parse.urlsplit(url).hostname != "api.github.com":
            raise ValueError("GitHub credentials may only be sent to api.github.com")
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(Redirect()).open(request, timeout=40) as response:
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Download exceeded its size limit")
    return payload


def api(path):
    repository = os.environ["GITHUB_REPOSITORY"]
    return json.loads(fetch(f"https://api.github.com/repos/{repository}/{path}", True))


def artifacts(name=None):
    result = []
    for page in range(1, 11):
        query = {"per_page": 100, "page": page}
        if name:
            query["name"] = name
        batch = api("actions/artifacts?" + urllib.parse.urlencode(query))["artifacts"]
        result.extend(a for a in batch if not a["expired"])
        if len(batch) < 100:
            return result
    raise ValueError("Too many artifacts to inspect safely")


def artifact_file(artifact, filename):
    data = fetch(artifact["archive_download_url"], True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo(filename)
        if info.file_size > 8 * 1024 * 1024:
            raise ValueError("Artifact payload too large")
        return archive.read(info)


def output(name, value):
    with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
        stream.write(f"{name}={value}\n")


def state_name():
    account = os.environ["APPLE_ID"].strip().lower().encode()
    return "free-sign-state-" + hashlib.sha256(account).hexdigest()[:16]


def key(password, salt):
    if len(password) < 20:
        raise ValueError("SIGNING_STATE_PASSWORD must contain at least 20 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())


def seal(data, password):
    salt, nonce = os.urandom(16), os.urandom(12)
    return b"ASFS1" + salt + nonce + AESGCM(key(password, salt)).encrypt(nonce, data, b"ASFS1")


def unseal(data, password):
    if data[:5] != b"ASFS1" or len(data) < 49:
        raise ValueError("Unsupported encrypted state format")
    return AESGCM(key(password, data[5:21])).decrypt(data[21:33], data[33:], b"ASFS1")


def restore():
    directory = Path(os.environ["SIGNING_STATE_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    key(os.environ["SIGNING_STATE_PASSWORD"], bytes(16))
    output("state_name", state_name())
    candidates = artifacts(state_name())
    candidates = [a for a in candidates if a.get("workflow_run", {}).get("head_branch") in ("main", "self-sign")]
    if not candidates:
        print("No previous encrypted state found. This run will create signing state.")
        return
    latest = max(candidates, key=lambda a: a["id"])
    data = unseal(artifact_file(latest, "state.enc"), os.environ["SIGNING_STATE_PASSWORD"])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            target = directory / entry.filename
            if not target.resolve().is_relative_to(directory.resolve()) or entry.file_size > 4 * 1024 * 1024:
                raise ValueError("Invalid state archive")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
            target.chmod(0o600)
    print("Restored encrypted signing state.")


def save():
    directory = Path(os.environ["SIGNING_STATE_DIR"])
    files = [p for p in directory.rglob("*") if p.is_file()]
    if not files:
        return
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(directory).as_posix())
    Path(os.environ["STATE_ARCHIVE"]).write_bytes(seal(buffer.getvalue(), os.environ["SIGNING_STATE_PASSWORD"]))


def mailbox():
    return Path(os.environ["SIGNING_MAILBOX_DIR"])


def initialize():
    directory = mailbox()
    directory.mkdir(parents=True, exist_ok=True)
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path = directory / "private.pem"
    private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    private_path.chmod(0o600)
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    request = {"id": str(uuid.uuid4()), "public_key": public, "run_id": os.environ["GITHUB_RUN_ID"]}
    (directory / "request.json").write_text(json.dumps(request))


def wait_code():
    directory = mailbox()
    request = json.loads((directory / "request.json").read_text())
    private = serialization.load_pem_private_key((directory / "private.pem").read_bytes(), None)
    seen_path = directory / "seen.json"
    seen = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        for artifact in artifacts(f"free-sign-code-{request['run_id']}"):
            if artifact["id"] in seen:
                continue
            seen.add(artifact["id"])
            seen_path.write_text(json.dumps(list(seen)))
            packet = artifact_file(artifact, "code.enc")
            try:
                message = json.loads(private.decrypt(packet, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)))
            except (ValueError, json.JSONDecodeError):
                continue
            if message.get("request_id") == request["id"] and re.fullmatch(r"[0-9]{6}", message.get("code", "")):
                sys.stdout.write(message["code"])
                return
        time.sleep(8)
    raise ValueError("No verification code received within ten minutes")


def deliver():
    code = os.environ.get("APPLE_2FA_CODE", "").strip()
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("Set APPLE_2FA_CODE to the six-digit Apple verification code")
    target = os.environ.get("TARGET_RUN_ID", "").strip()
    if target and not target.isdigit():
        raise ValueError("Target run ID must be numeric")
    active = api("actions/workflows/free-sign.yml/runs?status=in_progress&per_page=100")["workflow_runs"]
    active_ids = {str(run["id"]) for run in active}
    candidates = []
    for run in active:
        if target and str(run["id"]) != target:
            continue
        name = f"free-sign-request-{run['id']}-{run['run_attempt']}"
        candidates.extend(a for a in artifacts(name) if str(a["workflow_run"]["id"]) in active_ids)
    if target:
        candidates = [a for a in candidates if str(a["workflow_run"]["id"]) == target]
    if not candidates:
        raise ValueError("No active signing request found. Start a Sign IPA run first.")
    run_ids = {a["workflow_run"]["id"] for a in candidates}
    if len(run_ids) != 1:
        raise ValueError("Multiple sign-in runs are active. Fill in the target run ID.")
    request = json.loads(artifact_file(max(candidates, key=lambda a: a["id"]), "request.json"))
    public = serialization.load_pem_public_key(request["public_key"].encode())
    message = json.dumps({"request_id": request["id"], "code": code}).encode()
    encrypted = public.encrypt(message, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    Path(os.environ["CODE_ARCHIVE"]).write_bytes(encrypted)
    output("target_run_id", request["run_id"])
    print("Verification code encrypted for the waiting signing run.")


def download():
    release = json.loads(fetch("https://api.github.com/repos/Lakr233/Asspp/releases/latest"))
    asset = next(a for a in release["assets"] if a["name"] == "Asspp.ipa")
    data = fetch(asset["browser_download_url"], limit=600 * 1024 * 1024)
    if (asset.get("digest") or "").startswith("sha256:"):
        if hashlib.sha256(data).hexdigest() != asset["digest"].split(":", 1)[1]:
            raise ValueError("IPA checksum mismatch")
    Path(os.environ["INPUT_IPA"]).write_bytes(data)
    print("Downloaded upstream Asspp release " + release["tag_name"])


def package():
    app = Path(Path(os.environ["SIGNED_APP_PATH_FILE"]).read_text().strip()).resolve()
    if app.suffix != ".app" or not app.is_dir():
        raise ValueError("The signer did not return an app bundle")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True, capture_output=True)
    result = subprocess.run(["security", "cms", "-D", "-i", str(app / "embedded.mobileprovision")], check=True, capture_output=True)
    profile = plistlib.loads(result.stdout)
    info = plistlib.loads((app / "Info.plist").read_bytes())
    if os.environ["IPHONE_UDID"] not in profile.get("ProvisionedDevices", []):
        raise ValueError("The signed profile does not include the target iPhone")
    if profile["ExpirationDate"].replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise ValueError("The signed profile has expired")
    pattern = profile["Entitlements"]["application-identifier"].split(".", 1)[1]
    identifier = info["CFBundleIdentifier"]
    matches = identifier.startswith(pattern[:-1]) if pattern.endswith("*") else identifier == pattern
    if not matches or 1 not in info.get("UIDeviceFamily", []):
        raise ValueError("The signed IPA has an incompatible app identifier or device family")
    package_dir = Path(os.environ["SIGNING_MAILBOX_DIR"]).parent / "signed-package"
    (package_dir / "Payload").mkdir(parents=True, exist_ok=True)
    shutil.copytree(app, package_dir / "Payload" / app.name, symlinks=True)
    subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", str(package_dir), os.environ["SIGNED_IPA"]], check=True)
    print("Signed IPA passed signature, device, bundle ID and profile expiry checks.")


if __name__ == "__main__":
    commands = {"restore": restore, "save": save, "init": initialize, "wait-code": wait_code, "deliver": deliver, "download": download, "package": package}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=commands)
    args = parser.parse_args()
    try:
        commands[args.command]()
    except Exception:
        # Protocol payloads and cryptographic state must never enter Actions logs.
        print(f"::error::{args.command} failed. Check required Secrets, artifact availability, encryption password and the preceding status messages.", file=sys.stderr)
        sys.exit(1)
