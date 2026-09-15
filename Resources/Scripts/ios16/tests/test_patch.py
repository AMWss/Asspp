from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apply_compat import apply

ROOT = Path(__file__).resolve().parents[4]
PATCH = ROOT / "Resources/Patches/ios16.patch"
BASE = (ROOT / "Resources/Patches/ios16-base.txt").read_text().strip()


class PatchTests(unittest.TestCase):
    def test_recorded_upstream_becomes_reviewed_source(self):
        paths = subprocess.check_output(["git", "apply", "--numstat", str(PATCH)], cwd=ROOT, text=True)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            for line in paths.splitlines():
                name = line.split("\t", 2)[2]
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(subprocess.check_output(["git", "show", f"{BASE}:{name}"], cwd=ROOT))
            apply(source, PATCH)
            for line in paths.splitlines():
                name = line.split("\t", 2)[2]
                self.assertEqual((source / name).read_text(encoding="utf-8"), (ROOT / name).read_text(encoding="utf-8"), name)

    def test_conflict_stops_without_partial_modifications(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "a.txt").write_text("old\n")
            (root / "b.txt").write_text("upstream changed\n")
            patch = root / "test.patch"
            patch.write_text("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n"
                             "diff --git a/b.txt b/b.txt\n--- a/b.txt\n+++ b/b.txt\n@@ -1 +1 @@\n-old\n+new\n")
            with self.assertRaises(subprocess.CalledProcessError):
                apply(root, patch)
            self.assertEqual((root / "a.txt").read_text(), "old\n")
            self.assertEqual((root / "b.txt").read_text(), "upstream changed\n")


if __name__ == "__main__":
    unittest.main()
