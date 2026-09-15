from copy import deepcopy
from datetime import datetime, timedelta
import html
from pathlib import Path
import plistlib
import re
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from make_ota import generate
from verify_ipa import validate_info, validate_profile, verify
from verify_macho import minimum_versions


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.info = {
            "MinimumOSVersion": "16.0", "UIDeviceFamily": [2],
            "CFBundleIdentifier": "example.Asspp", "CFBundleVersion": "42",
            "CFBundleShortVersionString": "4.2.0",
        }
        self.profile = {
            "ExpirationDate": datetime.now() + timedelta(days=30),
            "ProvisionedDevices": ["EXAMPLE-DEVICE"], "ApplicationIdentifierPrefix": ["TEAM"],
            "Entitlements": {"application-identifier": "TEAM.example.Asspp", "get-task-allow": False},
        }

    def test_ios16_ipad_accepted(self):
        validate_info(self.info)
        validate_profile(self.profile, self.info)
        self.info["MinimumOSVersion"] = "16.0.0"
        validate_info(self.info)

    def test_iphone_ota_cannot_publish_ipad_only_or_ios26_build(self):
        with self.assertRaises(ValueError):
            validate_info(self.info, "iphone")
        iphone = self.info | {"UIDeviceFamily": [1, 2], "MinimumOSVersion": "17.0"}
        validate_info(iphone, "iphone")
        with self.assertRaises(ValueError):
            validate_info(iphone | {"MinimumOSVersion": "26.0"}, "iphone")

    def test_macho_does_not_confuse_linker_or_sdk_version_with_minimum_os(self):
        output = "cmd LC_BUILD_VERSION\ncmdsize 32\nplatform IOS\nminos 16.0\nsdk 26.2\nntools 1\ntool LD\nversion 1230.1\n"
        self.assertEqual(minimum_versions(output), ["16.0"])
        self.assertEqual(minimum_versions("cmd LC_VERSION_MIN_IPHONEOS\ncmdsize 16\nversion 15.0\nsdk 17.0\n"), ["15.0"])

    def test_newer_os_or_iphone_only_rejected(self):
        for field, value in [("MinimumOSVersion", "17.0"), ("MinimumOSVersion", "16.1"), ("UIDeviceFamily", [1])]:
            with self.subTest(field=field, value=value):
                info = self.info | {field: value}
                with self.assertRaises(ValueError):
                    validate_info(info)

    def test_invalid_profiles_rejected(self):
        for change in ("expired", "store", "development", "wrong-app", "wrong-prefix"):
            profile = deepcopy(self.profile)
            if change == "expired":
                profile["ExpirationDate"] = datetime.now() - timedelta(days=1)
            elif change == "store":
                del profile["ProvisionedDevices"]
            elif change == "development":
                profile["Entitlements"]["get-task-allow"] = True
            elif change == "wrong-app":
                profile["Entitlements"]["application-identifier"] = "TEAM.other.app"
            else:
                profile["ApplicationIdentifierPrefix"] = ["OTHER"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_profile(profile, self.info)

    def test_wildcard_and_enterprise_profiles(self):
        self.profile["Entitlements"]["application-identifier"] = "TEAM.example.*"
        validate_profile(self.profile, self.info)
        del self.profile["ProvisionedDevices"]
        self.profile["ProvisionsAllDevices"] = True
        validate_profile(self.profile, self.info)

    def test_manifest_matches_ipa_and_nested_url_roundtrips(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            base = "https://example.com/my-repo/ios/latest"
            ipa_url = "https://github.com/user/repo/releases/download/build/app.ipa"
            generate(output, base, ipa_url, self.info, "source <tag>")
            manifest = plistlib.loads((output / "manifest.plist").read_bytes())["items"][0]
            self.assertEqual(manifest["metadata"]["bundle-version"], "42")
            self.assertEqual(manifest["metadata"]["bundle-identifier"], "example.Asspp")
            self.assertEqual(manifest["assets"][0]["url"], ipa_url)
            page = (output / "install.html").read_text(encoding="utf-8")
            link = html.unescape(re.search(r'href="(itms-services:[^"]+)"', page)[1])
            self.assertEqual(parse_qs(urlsplit(link).query)["url"], [base + "/manifest.plist"])
            self.assertIn("source &lt;tag&gt;", page)

    def test_unsigned_ipa_does_not_pass_signed_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.ipa"
            with zipfile.ZipFile(path, "w") as ipa:
                ipa.writestr("Payload/Asspp.app/Info.plist", plistlib.dumps(self.info))
            self.assertEqual(verify(path, signed=False), self.info)
            with self.assertRaises(KeyError):
                verify(path, signed=True)

    def test_insecure_ota_url_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            with self.assertRaises(ValueError):
                generate(output, "http://example.com", "https://example.com/app.ipa", self.info, "test")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
