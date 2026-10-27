import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ofa import ROOT, cli
from ofa.errors import GuardError


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        pkg = Path(self.tmp.name) / "fakecmds"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "boom.py").write_text("raise RuntimeError('broken at import')\n")
        (pkg / "needs_dep.py").write_text("import ofa_no_such_dependency\n")
        (pkg / "guarded.py").write_text(
            "from ofa.errors import GuardError\n"
            "def register(sub):\n"
            "    p = sub.add_parser('guarded')\n"
            "    def handler(args):\n"
            "        raise GuardError('BAD_NAME', 'db xm does not match ^ofa_demo_')\n"
            "    p.set_defaults(func=handler)\n"
        )
        sys.path.insert(0, self.tmp.name)
        self.addCleanup(sys.path.remove, self.tmp.name)
        self.addCleanup(lambda: [sys.modules.pop(m) for m in list(sys.modules) if m.startswith("fakecmds")])

    def run_main(self, argv, commands):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(argv, commands=commands, package="fakecmds")
        return code, err.getvalue()

    def test_missing_module_is_not_implemented(self):
        code, err = self.run_main(["lint-plan"], ("lint_plan",))
        self.assertEqual(code, 2)
        self.assertIn("not implemented", err)

    def test_module_raising_on_import_exits_4(self):
        code, err = self.run_main(["boom"], ("boom",))
        self.assertEqual(code, 4)
        self.assertEqual(err.strip(), "ofa: 4: cannot load command boom: RuntimeError")

    def test_missing_dependency_inside_module_exits_4(self):
        code, err = self.run_main(["needs-dep"], ("needs_dep",))
        self.assertEqual(code, 4)
        self.assertIn("cannot load command needs_dep: ModuleNotFoundError", err)

    def test_ofa_error_maps_to_exit_code_and_label(self):
        code, err = self.run_main(["guarded"], ("guarded",))
        self.assertEqual(code, 3)
        self.assertEqual(err.strip(), "ofa: BAD_NAME: db xm does not match ^ofa_demo_")

    def test_cli_names(self):
        names = [cli.cli_name(n) for n in cli.COMMANDS]
        self.assertEqual(len(names), 16)  # the plan's 15, plus `source` (T24)
        self.assertIn("lint-plan", names)
        self.assertIn("source", names)
        self.assertNotIn("lint_plan", names)

    def test_launcher_help_and_stubs(self):
        ofa = str(ROOT / "bin" / "ofa")
        help_out = subprocess.run([ofa, "--help"], capture_output=True, text=True)
        self.assertEqual(help_out.returncode, 0)
        for name in cli.COMMANDS:
            self.assertIn(cli.cli_name(name), help_out.stdout)
        # Commands become real one task at a time; only the ones still missing must be stubs.
        missing = [n for n in cli.COMMANDS if importlib.util.find_spec(f"ofa.commands.{n}") is None]
        # T18 made lint-plan real; it must still be listed exactly once.
        self.assertEqual(help_out.stdout.count("lint-plan"), 1)
        for name in map(cli.cli_name, missing):
            r = subprocess.run([ofa, name], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("not implemented", r.stderr)

    def test_guard_error_without_message(self):
        e = GuardError("NOT_REGISTERED")
        self.assertEqual((e.label, e.msg, e.exit_code), ("NOT_REGISTERED", "NOT_REGISTERED", 3))


class SourceCommandTest(unittest.TestCase):
    # T24: the skill read the maintainer's CLAUDE.md to find the Odoo source; `ofa source` answers that instead.
    def test_prints_addons_path_and_core_from_the_odoo_conf(self):
        import json
        from types import SimpleNamespace
        from unittest import mock

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, tmp)
        for d in ("enterprise", "odoo/addons", "odoo/odoo/addons"):
            (tmp / d).mkdir(parents=True)
        (tmp / "odoo" / "odoo-bin").write_text("")
        conf = tmp / "odoo.conf"
        conf.write_text(f"[options]\naddons_path = {tmp}/enterprise, {tmp}/odoo/addons, {tmp}/missing\n")
        server = SimpleNamespace(odoo_conf=conf, odoo_bin=tmp / "odoo" / "odoo-bin", odoo_version="20.0",
                                 edition="enterprise")
        out = io.StringIO()
        with mock.patch("ofa.config.load", return_value=SimpleNamespace(server=server)), \
                contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["source", "--json"]), 0)
        paths = [(r["kind"], r["path"]) for r in json.loads(out.getvalue())["paths"]]
        self.assertEqual(paths, [("addons", f"{tmp}/enterprise"), ("addons", f"{tmp}/odoo/addons"),
                                 ("addons", f"{tmp}/odoo/odoo/addons"), ("core", f"{tmp}/odoo/odoo")])
