import contextlib
import io
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from ofa import ROOT, cli, knowledge
from ofa.commands import stale
from ofa.errors import EnvError

FIXTURES = ROOT / "tests" / "fixtures" / "knowledge"
AREAS = ("sales_crm", "purchase_inventory", "accounting", "multi_company", "l10n_mx")

GOOD_FM = """---
title: T
area: a
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/x.html, odoo/addons/sale/models/x.py@20.0]
verified_on: 2026-10-23
verified_against: [source, live]
modules: [sale]
---
"""
SECTIONS = "\n## When to use\nx\n\n## Configuration\nx\n\n## How to verify\nx\n\n## Pitfalls\nx\n\n## Alternatives\nx\n"


def run_ofa(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv, commands=("stale",))
    return code, out.getvalue(), err.getvalue()


class FrontMatterTest(unittest.TestCase):
    def test_parses_scalars_and_flow_lists(self):
        meta, body = knowledge.parse_front_matter(GOOD_FM + SECTIONS)
        self.assertEqual(meta["odoo_version"], "20.0")
        self.assertEqual(meta["source"], ["https://www.odoo.com/documentation/20.0/x.html",
                                          "odoo/addons/sale/models/x.py@20.0"])
        self.assertEqual(meta["verified_against"], ["source", "live"])
        self.assertIn("## When to use", body)
        self.assertEqual(knowledge.check_meta(meta, "20.0", "a"), [])

    def test_empty_list_and_quoted_scalar(self):
        meta, _ = knowledge.parse_front_matter('---\ntitle: "A: b"\nmodels: []\n---\n')
        self.assertEqual(meta, {"title": "A: b", "models": []})

    def test_rejections(self):
        cases = {
            "no front matter": "# Title\n",
            "nested map": "---\nsettings:\n  a: b\n---\n",
            "indented": "---\ntitle: x\n  more: y\n---\n",
            "unterminated list": "---\nmodels: [a, b\n---\n",
            "nested list": "---\nmodels: [a, [b]]\n---\n",
            "flow map": "---\nx: {a: 1}\n---\n",
            "no closing fence": "---\ntitle: x\n",
            "duplicate": "---\ntitle: x\ntitle: y\n---\n",
            "not key value": "---\njust text\n---\n",
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(knowledge.FrontMatterError):
                knowledge.parse_front_matter(text)

    def test_meta_checks(self):
        meta, _ = knowledge.parse_front_matter(GOOD_FM)
        bad = dict(meta, edition="pro", verified_on="23/10/2026", verified_against=["guess"], source=[],
                   modules="sale")
        del bad["title"]
        problems = " | ".join(knowledge.check_meta(bad, "19.0", "b"))
        for needle in ("missing key: title", "edition", "verified_on", "verified_against: unknown guess",
                       "source must cite", "modules must be a flow list", "odoo_version 20.0", "area a"):
            self.assertIn(needle, problems)


class SectionTest(unittest.TestCase):
    def test_all_sections_ok(self):
        self.assertEqual(knowledge.check_sections(SECTIONS + "\n## Mexico notes\nx\n"), [])

    def test_missing_section(self):
        body = SECTIONS.replace("## How to verify", "## Verify")
        self.assertEqual(knowledge.check_sections(body), ["missing section: ## How to verify"])

    def test_out_of_order(self):
        body = "## Configuration\n## When to use\n## How to verify\n## Pitfalls\n## Alternatives\n"
        self.assertIn("out of order", knowledge.check_sections(body)[0])

    def test_headings_inside_code_fences_do_not_count(self):
        body = "```\n## When to use\n```\n" + SECTIONS.replace("## When to use\n", "")
        self.assertEqual(knowledge.check_sections(body), ["missing section: ## When to use"])


class IndexLinkTest(unittest.TestCase):
    def test_linked_area_indexes(self):
        text = "- [A](sales_crm/INDEX.md)\n- [B](l10n_mx/INDEX.md) [again](sales_crm/INDEX.md) [x](other.md)"
        self.assertEqual(knowledge.linked_area_indexes(text), ["sales_crm", "l10n_mx"])

    def test_real_top_index_links_the_five_areas(self):
        text = (ROOT / "knowledge" / "20.0" / "INDEX.md").read_text()
        self.assertEqual(sorted(knowledge.linked_area_indexes(text)), sorted(AREAS))


class StaleCommandTest(unittest.TestCase):
    def test_lists_fixture_entries(self):
        code, out, _ = run_ofa(["stale", "--root", str(FIXTURES), "--since", "2099-01-01"])
        self.assertEqual(code, 0)
        names = sorted(Path(p).name for p in out.splitlines())
        self.assertEqual(names, ["line_discounts.md", "missing_how_to_verify.md", "missing_verified_on.md",
                                 "nested_map.md"])

    def test_since_filters_and_unreadable_dates_stay_listed(self):
        code, out, _ = run_ofa(["stale", "--root", str(FIXTURES), "--since", "2026-10-23"])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(Path(p).name for p in out.splitlines()), ["missing_verified_on.md", "nested_map.md"])
        code, out, _ = run_ofa(["stale", "--root", str(FIXTURES), "--since", "2026-10-23", "--area", "good"])
        self.assertEqual((code, out), (0, ""))

    def test_bad_since_is_usage_error(self):
        code, _, err = run_ofa(["stale", "--root", str(FIXTURES), "--since", "2099-1-1"])
        self.assertEqual(code, 2)
        self.assertIn("--since", err)

    def test_lint_good_and_bad(self):
        code, out, _ = run_ofa(["stale", "--lint", "--root", str(FIXTURES), "--area", "good"])
        self.assertEqual(code, 0)
        self.assertIn("ok: 1 entry checked", out)
        code, _, err = run_ofa(["stale", "--lint", "--root", str(FIXTURES), "--area", "bad"])
        self.assertEqual(code, 2)
        self.assertIn("missing_verified_on.md: missing key: verified_on", err)
        self.assertIn("nested_map.md: line 9: empty value for 'settings'", err)
        self.assertIn("missing_how_to_verify.md: missing section: ## How to verify", err)
        self.assertIn("ofa: KNOWLEDGE_LINT: 3 problem(s) in 3 file(s)", err)

    def test_missing_area_or_area_index(self):
        code, _, err = run_ofa(["stale", "--lint", "--area", "nope", "--root", str(FIXTURES)])
        self.assertEqual(code, 2)
        self.assertIn("NO_AREA", err)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "20.0" / "x").mkdir(parents=True)
            for lint in ([], ["--lint"]):
                code, _, err = run_ofa(["stale", *lint, "--area", "x", "--root", tmp, "--since", "2099-01-01"])
                self.assertEqual(code, 2)
                self.assertIn("NO_AREA_INDEX", err)
            code, _, err = run_ofa(["stale", "--lint", "--root", tmp])
            self.assertEqual(code, 2)
            self.assertIn("missing version index", err)
            self.assertIn("missing area index", err)
        code, _, err = run_ofa(["stale", "--lint", "--area", "../20.0", "--root", str(FIXTURES)])
        self.assertEqual(code, 2)

    def test_missing_version_folder(self):
        code, _, err = run_ofa(["stale", "--lint", "--root", str(FIXTURES), "--version", "19.0"])
        self.assertEqual(code, 2)
        self.assertIn("NO_VERSION", err)

    def test_missing_area_indexes_only_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = Path(tmp) / "20.0"
            (v / "sales_crm").mkdir(parents=True)
            (v / "sales_crm" / "INDEX.md").write_text("# s\n")
            (v / "sales_crm" / "t.md").write_text(GOOD_FM.replace("area: a", "area: sales_crm") + SECTIONS)
            (v / "INDEX.md").write_text("[s](sales_crm/INDEX.md) [p](purchase_inventory/INDEX.md)\n")
            code, out, err = run_ofa(["stale", "--lint", "--root", tmp])
        self.assertEqual(code, 0, err)
        self.assertEqual(err.count("WARN missing area index:"), 1)
        self.assertIn("purchase_inventory/INDEX.md", err)
        self.assertIn("ok: 1 entry checked", out)

    def test_real_tree_lints_with_five_warnings(self):
        code, _, err = run_ofa(["stale", "--lint", "--since", "2099-01-01"])
        self.assertEqual(code, 0, err)
        self.assertEqual(err.count("WARN missing area index:"), 5 - sum(
            (ROOT / "knowledge" / "20.0" / a / "INDEX.md").is_file() for a in AREAS))


class DefaultSinceTest(unittest.TestCase):
    """The default --since comes from ofa.config (T05); stub it so this test never needs the real module."""

    def stub_config(self, load):
        mod = types.ModuleType("ofa.config")
        mod.load = load
        patcher = mock.patch.dict(sys.modules, {"ofa.config": mod})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_odoo_checkout_head_date(self):
        server = types.SimpleNamespace(odoo_bin="/somewhere/odoo/odoo-bin")
        self.stub_config(lambda: types.SimpleNamespace(server=server))
        done = subprocess.CompletedProcess([], 0, stdout="2026-10-23\n", stderr="")
        with mock.patch.object(stale.subprocess, "run", return_value=done) as run:
            self.assertEqual(stale.default_since(), "2026-10-23")
        self.assertEqual(run.call_args.args[0], ["git", "-C", "/somewhere/odoo", "log", "-1", "--format=%cs"])

    def test_since_required_when_config_fails(self):
        def boom():
            raise EnvError("NO_CONFIG", "config.toml not found")
        self.stub_config(boom)
        code, _, err = run_ofa(["stale", "--root", str(FIXTURES)])
        self.assertEqual(code, 2)
        self.assertIn("--since is required", err)

    def test_since_required_when_config_module_missing(self):
        patcher = mock.patch.dict(sys.modules, {"ofa.config": None})  # None makes import raise ImportError
        patcher.start()
        self.addCleanup(patcher.stop)
        code, _, err = run_ofa(["stale", "--root", str(FIXTURES)])
        self.assertEqual(code, 2)
        self.assertIn("--since is required", err)

    def test_since_required_when_git_fails(self):
        server = types.SimpleNamespace(odoo_bin="/nowhere/odoo-bin")
        self.stub_config(lambda: types.SimpleNamespace(server=server))
        failed = subprocess.CompletedProcess([], 128, stdout="", stderr="fatal")
        with mock.patch.object(stale.subprocess, "run", return_value=failed):
            code, _, err = run_ofa(["stale", "--root", str(FIXTURES)])
        self.assertEqual(code, 2)
        self.assertIn("--since is required", err)

    def test_lint_does_not_need_since(self):
        patcher = mock.patch.dict(sys.modules, {"ofa.config": None})
        patcher.start()
        self.addCleanup(patcher.stop)
        code, _, _ = run_ofa(["stale", "--lint", "--root", str(FIXTURES), "--area", "good"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
