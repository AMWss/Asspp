import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import zipfile

from cryptography.exceptions import InvalidTag

spec = importlib.util.spec_from_file_location("free_sign_actions", Path(__file__).resolve().parents[1] / "actions.py")
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)


class SigningTransportTests(unittest.TestCase):
    def test_sidestore_download_chooses_only_official_nightly_ipa(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.ipa'
            payload = b'PK-test-sidestore'
            release = {'tag_name': 'nightly', 'assets': [
                {'name': 'build-logs.zip'},
                {'name': 'SideStore.ipa', 'browser_download_url': 'https://github.com/SideStore/SideStore/releases/download/nightly/SideStore.ipa', 'digest': 'sha256:' + actions.hashlib.sha256(payload).hexdigest()}]}
            with patch.dict(os.environ, {'SIGNING_APPLICATION': 'SideStore', 'INPUT_IPA': str(path), 'GITHUB_OUTPUT': str(Path(directory) / 'output')}), patch.object(actions, 'fetch', side_effect=[json.dumps(release).encode(), payload]) as fetch:
                actions.download()
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(fetch.call_args_list[0].args[0], 'https://api.github.com/repos/SideStore/SideStore/releases/tags/nightly')

    def test_sidestore_private_package_browser_crypto_compatibility(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'SideStore.ipa'
            raw.write_bytes(b'PK-private-signing-identity-test')
            target = root / 'protected'
            password = 'local-test-password-over-20-characters'
            with patch.dict(os.environ, {'SIGNED_IPA': str(raw), 'PROTECTED_PACKAGE_DIR': str(target), 'SIGNING_STATE_PASSWORD': password}):
                actions.protect_package()
            encrypted = (target / 'SideStore-signed.ipa.enc').read_bytes()
            self.assertNotIn(b'private-signing-identity', encrypted)
            self.assertEqual(sorted(p.name for p in target.iterdir()), ['README.txt', 'SideStore-signed.ipa.enc', 'decrypt-package.html'])
            script = """const fs=require('fs'); const b=fs.readFileSync(process.argv[1]); (async()=>{const material=await crypto.subtle.importKey('raw',new TextEncoder().encode(process.argv[2]),'PBKDF2',false,['deriveKey']); const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:b.subarray(5,21),iterations:600000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['decrypt']);const out=await crypto.subtle.decrypt({name:'AES-GCM',iv:b.subarray(21,33),additionalData:b.subarray(0,33)},key,b.subarray(33));process.stdout.write(Buffer.from(out));})().catch(()=>process.exit(2));"""
            result = subprocess.run(['node', '-e', script, str(target / 'SideStore-signed.ipa.enc'), password], capture_output=True, check=True)
            self.assertEqual(result.stdout, raw.read_bytes())
            result = subprocess.run(['node', '-e', script, str(target / 'SideStore-signed.ipa.enc'), password + 'wrong'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_state_encryption_authenticates_password_and_contents(self):
        password = "a-test-password-with-more-than-20-characters"
        encrypted = actions.seal(b"private signing key", password)
        self.assertNotIn(b"private signing key", encrypted)
        self.assertEqual(actions.unseal(encrypted, password), b"private signing key")
        with self.assertRaises(InvalidTag):
            actions.unseal(encrypted, password + "wrong")
        changed = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
        with self.assertRaises(InvalidTag):
            actions.unseal(changed, password)

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            actions.seal(b"key", "short")

    def test_cross_host_redirect_drops_github_authorization(self):
        request = urllib.request.Request("https://api.github.com/artifact", headers={"Authorization": "Bearer private"})
        redirected = actions.Redirect().redirect_request(request, None, 302, "Found", {}, "https://storage.example/artifact")
        self.assertIsNone(redirected.get_header("Authorization"))
        with self.assertRaises(ValueError):
            actions.Redirect().redirect_request(request, None, 302, "Found", {}, "http://storage.example/artifact")

    def test_explicit_github_credentials_rejected_for_other_hosts(self):
        with self.assertRaises(ValueError):
            actions.fetch("https://example.com/ipa", authenticated=True)

    def test_state_restore_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("../outside", "private")
            password = "a-test-password-with-more-than-20-characters"
            environment = {"SIGNING_STATE_DIR": str(Path(directory) / "state"), "APPLE_ID": "test@example.com", "SIGNING_STATE_PASSWORD": password, "GITHUB_OUTPUT": str(Path(directory) / "output")}
            encrypted = actions.seal(buffer.getvalue(), password)
            artifact = {"id": 1, "workflow_run": {"head_branch": "main"}}
            with patch.dict(os.environ, environment), patch.object(actions, "artifacts", return_value=[artifact]), patch.object(actions, "artifact_file", return_value=encrypted):
                with self.assertRaises(ValueError):
                    actions.restore()
            self.assertFalse((Path(directory) / "outside").exists())

    def test_live_code_delivery_and_no_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {"SIGNING_MAILBOX_DIR": str(root), "GITHUB_RUN_ID": "123", "CODE_ARCHIVE": str(root / "code.enc"), "GITHUB_OUTPUT": str(root / "output"), "APPLE_2FA_CODE": "123456", "TARGET_RUN_ID": ""}
            request_artifact = {"id": 1, "name": "free-sign-request-123-1", "workflow_run": {"id": 123}}
            code_artifact = {"id": 2, "name": "free-sign-code-123", "workflow_run": {"id": 124}}
            with patch.dict(os.environ, environment):
                actions.initialize()
                with patch.object(actions, "api", return_value={"workflow_runs": [{"id": 123, "run_attempt": 1}]}), patch.object(actions, "artifacts", return_value=[request_artifact]), patch.object(actions, "artifact_file", return_value=(root / "request.json").read_bytes()):
                    actions.deliver()
                packet = (root / "code.enc").read_bytes()
                self.assertNotIn(b"123456", packet)
                with patch.object(actions, "artifacts", return_value=[code_artifact]), patch.object(actions, "artifact_file", return_value=packet), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    actions.wait_code()
                self.assertEqual(stdout.getvalue(), "123456")
                self.assertEqual(json.loads((root / "seen.json").read_text()), [2])
                with patch.object(actions, "artifacts", return_value=[code_artifact]), patch.object(actions.time, "monotonic", side_effect=[0, 1, 601]), patch.object(actions.time, "sleep"):
                    with self.assertRaises(ValueError):
                        actions.wait_code()

    def test_wrong_password_does_not_overwrite_existing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state").mkdir()
            (root / "state" / "key").write_text("existing")
            environment = {"SIGNING_STATE_DIR": str(root / "state"), "APPLE_ID": "test@example.com", "SIGNING_STATE_PASSWORD": "a-long-but-incorrect-password-value", "GITHUB_OUTPUT": str(root / "output")}
            encrypted = actions.seal(b"archive", "another-long-password-value")
            artifact = {"id": 1, "workflow_run": {"head_branch": "main"}}
            with patch.dict(os.environ, environment), patch.object(actions, "artifacts", return_value=[artifact]), patch.object(actions, "artifact_file", return_value=encrypted):
                with self.assertRaises(InvalidTag):
                    actions.restore()
            self.assertEqual((root / "state" / "key").read_text(), "existing")

    def test_request_new_code_requires_no_code_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {"SIGNING_MAILBOX_DIR": str(root), "GITHUB_RUN_ID": "123", "CODE_ARCHIVE": str(root / "code.enc"), "GITHUB_OUTPUT": str(root / "output"), "APPLE_2FA_CODE": "", "TARGET_RUN_ID": "", "MESSAGE_KIND": "Request new code"}
            request_artifact = {"id": 1, "name": "free-sign-request-123-1", "workflow_run": {"id": 123}}
            code_artifact = {"id": 2, "name": "free-sign-code-123", "workflow_run": {"id": 124}}
            with patch.dict(os.environ, environment):
                actions.initialize()
                with patch.object(actions, "api", return_value={"workflow_runs": [{"id": 123, "run_attempt": 1}]}), patch.object(actions, "artifacts", return_value=[request_artifact]), patch.object(actions, "artifact_file", return_value=(root / "request.json").read_bytes()):
                    actions.deliver()
                packet = (root / "code.enc").read_bytes()
                with patch.object(actions, "artifacts", return_value=[code_artifact]), patch.object(actions, "artifact_file", return_value=packet), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    actions.wait_code()
                self.assertEqual(stdout.getvalue(), "RESEND")


if __name__ == "__main__":
    unittest.main()
