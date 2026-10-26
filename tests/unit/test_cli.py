import contextlib
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
        self.assertEqual(len(names), 15)
        self.assertIn("lint-plan", names)
        self.assertNotIn("lint_plan", names)

    def test_launcher_help_and_stubs(self):
        ofa = str(ROOT / "bin" / "ofa")
        help_out = subprocess.run([ofa, "--help"], capture_output=True, text=True)
        self.assertEqual(help_out.returncode, 0)
        for name in cli.COMMANDS:
            self.assertIn(cli.cli_name(name), help_out.stdout)
        for name in ("apply", "lint-plan"):
            r = subprocess.run([ofa, name], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("not implemented", r.stderr)

    def test_guard_error_without_message(self):
        e = GuardError("NOT_REGISTERED")
        self.assertEqual((e.label, e.msg, e.exit_code), ("NOT_REGISTERED", "NOT_REGISTERED", 3))
