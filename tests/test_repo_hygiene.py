"""Repo hygiene: nothing private, proprietary or local-only is tracked or about to be.

Forbidden literals are assembled at runtime so this file never contains them.
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

from ofa import ROOT

SELF = "tests/test_repo_hygiene.py"
COMPANY = ("kala" + "pata").lower()
LICENSE_LITERALS = ("Odoo Proprietary" + " License", "OEEL" + "-1")
RFC_RE = re.compile(r"(?<![A-ZÑ&0-9])[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}(?![A-Z0-9])")
# SAT test RFCs verified by spike S5; filled in by the l10n_mx task.
RFC_ALLOWLIST = frozenset({
    "IVD920810GU2", "ZUÑ920208KL4",  # 20.0 MX demo companies 4 and 5, owners of the shipped demo CSDs
    "XIA190128J61", "ICV060329BY0",  # 20.0 l10n_mx_edi demo partners, accepted as receivers by the test PACs
    "XAXX010101000", "XEXX010101000",  # SAT generic RFCs (público en general, foreign receiver)
})
HOME_RE = re.compile(r"/(?:home|Users)/[^/\s\"']+/")
PLAN_DIR = "docs/" + "plan/"
KEYS_DIR = Path.home() / ".config" / "ofa" / "keys"


def rule_company(path, text):
    return COMPANY in text.lower()


def rule_proprietary_license(path, text):
    return any(lit in text for lit in LICENSE_LITERALS)


def rule_key_content(path, text, keys=None):
    keys = _load_keys() if keys is None else keys
    return any(k in text for k in keys)


def rule_rfc(path, text, allowlist=RFC_ALLOWLIST):
    return any(m not in allowlist for m in RFC_RE.findall(text))


def rule_md_links_plan(path, text):
    return path.endswith(".md") and PLAN_DIR in text


def _has_debug_key(obj):
    if isinstance(obj, dict):
        return "debug" in obj or any(_has_debug_key(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_debug_key(v) for v in obj)
    return False


def rule_example_leak(path, text):
    if not path.startswith("examples/"):
        return False
    if "Traceback (most recent call last)" in text or HOME_RE.search(text):
        return True
    if path.endswith(".json"):
        try:
            return _has_debug_key(json.loads(text))
        except ValueError:
            return re.search(r'"debug"\s*:', text) is not None
    return False


def rule_local_only_path(path, text):
    return path.startswith(PLAN_DIR) or path.startswith(".odoo/")


SOURCE_INDEX_RE = re.compile(r'"format"\s*:\s*"ofa\.source_index/')
SOURCE_INDEX_NAME = re.compile(r"(^|/)source_index_[0-9a-f]+\.json$")


def rule_source_index(path, text):
    """The source index is derived from Enterprise code: it lives in ~/.cache/ofa, never in the repo."""
    return bool(SOURCE_INDEX_NAME.search(path) or SOURCE_INDEX_RE.search(text))


RULES = (rule_company, rule_proprietary_license, rule_key_content, rule_rfc,
         rule_md_links_plan, rule_example_leak, rule_local_only_path, rule_source_index)


def _load_keys():
    if not KEYS_DIR.is_dir():
        return ()
    keys = []
    for f in KEYS_DIR.iterdir():
        if f.is_file():
            k = f.read_text(errors="ignore").strip()
            if k:
                keys.append(k)
    return tuple(keys)


def scanned_files():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.split("\0") if p and p != SELF)


def read_text(path):
    try:
        data = (ROOT / path).read_bytes()
    except (FileNotFoundError, IsADirectoryError):
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


class RepoHygieneTest(unittest.TestCase):
    def test_repo_is_clean(self):
        keys = _load_keys()
        violations = []
        for path in scanned_files():
            text = read_text(path)
            if rule_local_only_path(path, ""):
                violations.append((path, "rule_local_only_path"))
            if text is None:
                continue
            for rule in RULES:
                hit = rule(path, text, keys) if rule is rule_key_content else rule(path, text)
                if hit:
                    violations.append((path, rule.__name__))
        self.assertEqual(violations, [])

    def test_self_is_excluded(self):
        self.assertNotIn(SELF, scanned_files())


class RuleTest(unittest.TestCase):
    def test_company(self):
        self.assertTrue(rule_company("a.md", "Works for " + "KALA" + "PATA group"))
        self.assertFalse(rule_company("a.md", "a holding company"))

    def test_proprietary_license(self):
        self.assertTrue(rule_proprietary_license("m.py", "# License: " + "OEEL" + "-1"))
        self.assertTrue(rule_proprietary_license("m.py", "Odoo Proprietary" + " License v1.0"))
        self.assertFalse(rule_proprietary_license("m.py", "License: MIT"))

    def test_source_index(self):
        self.assertTrue(rule_source_index("x/source_index_d1ac0caa9554bf1d.json", "{}"))
        self.assertTrue(rule_source_index("cache.json", '{"format": "ofa.source_index/1", "models": {}}'))
        self.assertFalse(rule_source_index("src/ofa/source_index.py", 'FORMAT = "ofa.source_index/1"'))

    def test_key_content(self):
        self.assertTrue(rule_key_content("x.json", 'key "abc123secret"', keys=("abc123secret",)))
        self.assertFalse(rule_key_content("x.json", "nothing", keys=("abc123secret",)))
        self.assertFalse(rule_key_content("x.json", "nothing", keys=()))

    def test_rfc(self):
        rfc = "ABCD" + "800101" + "XY9"
        self.assertTrue(rule_rfc("a.md", f"RFC {rfc}."))
        self.assertTrue(rule_rfc("a.md", "Ñ&A" + "800101" + "XY9"))
        self.assertFalse(rule_rfc("a.md", f"RFC {rfc}.", allowlist=frozenset({rfc})))
        self.assertFalse(rule_rfc("a.md", "ABCD800101"))
        self.assertFalse(rule_rfc("a.md", "XABCD" + "800101" + "XY9Z"))

    def test_md_links_plan(self):
        self.assertTrue(rule_md_links_plan("README.md", "see " + PLAN_DIR + "spec.md"))
        self.assertFalse(rule_md_links_plan("src/x.py", PLAN_DIR))
        self.assertFalse(rule_md_links_plan("README.md", "see docs/setup.md"))

    def test_example_leak(self):
        self.assertTrue(rule_example_leak("examples/a/report.md", "Traceback (most recent call last):"))
        self.assertTrue(rule_example_leak("examples/a/report.md", "at /home/" + "someone/x.py"))
        self.assertTrue(rule_example_leak("examples/a/r.md", "/Users/" + "someone/x"))
        self.assertTrue(rule_example_leak("examples/a/r.json", '{"error": {"debug": "x"}}'))
        self.assertTrue(rule_example_leak("examples/a/r.json", '{"debug": 1'))
        self.assertFalse(rule_example_leak("examples/a/r.json", '{"error": {"name": "x"}}'))
        self.assertFalse(rule_example_leak("docs/a.md", "Traceback (most recent call last):"))

    def test_local_only_path(self):
        self.assertTrue(rule_local_only_path(PLAN_DIR + "spec.md", ""))
        self.assertTrue(rule_local_only_path(".odoo/odoo20.conf", ""))
        self.assertFalse(rule_local_only_path("docs/setup.md", ""))


if __name__ == "__main__":
    unittest.main()
