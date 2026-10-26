import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ofa import cli, report
from tests.fakeodoo import Response, error_body
from tests.unit.test_client import KEY, FakeCase
from tests.unit.test_scenario import FAIL_FILE, PASS_FILE, TRACE, script_sales

ARTIFACTS = ("test.json", "records.json", "screenshot_targets.json", "calls.jsonl", "report.md")


class TestCommandCase(FakeCase):
    def setUp(self):
        super().setUp()
        self.plan_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.plan_dir)
        (self.plan_dir / "plan.json").write_text(json.dumps({"format": "ofa.plan/1", "title": "Demo plan", "operations": []}))
        (self.plan_dir / "plan.approved").write_text(json.dumps({"sha256": "ab" * 32, "approved_at": "2026-10-26T00:00:00Z"}))
        patcher = mock.patch("ofa.config.load", return_value=self.cfg)
        patcher.start()
        self.addCleanup(patcher.stop)

    def ofa_test(self, *files, run=None):
        argv = ["test", "--target", "t1", "--plan-dir", str(self.plan_dir)]
        if run:
            argv += ["--run", run]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv + [str(f) for f in files])
        self.stdout, self.stderr = out.getvalue(), err.getvalue()
        return code

    def run_dir(self):
        return self.plan_dir / "runs" / self.stdout.strip()

    def read(self, name):
        return (self.run_dir() / name).read_text()


class ExitCodeTest(TestCommandCase):
    def test_all_pass_exit_0_and_artifacts(self):
        script_sales(self.fake)
        self.assertEqual(self.ofa_test(PASS_FILE), 0, self.stderr)
        run_id = self.stdout.strip()
        self.assertRegex(run_id, r"^\d{8}T\d{6}Z_t1$")
        for name in ARTIFACTS:
            self.assertTrue((self.run_dir() / name).is_file(), name)
        test = json.loads(self.read("test.json"))
        self.assertEqual(set(test), {"run_id", "target", "scenarios"})
        self.assertEqual((test["run_id"], test["target"]), (run_id, "t1"))
        sc = test["scenarios"][0]
        self.assertEqual((sc["id"], sc["status"]), ("quote_confirm_pass", "pass"))
        self.assertEqual(set(sc["steps"][0]), {"id", "status", "message", "records"})
        records = json.loads(self.read("records.json"))
        self.assertEqual(records["quote_confirm_pass"]["confirmed_order"][0]["state"], "sale")
        shots = json.loads(self.read("screenshot_targets.json"))
        self.assertEqual(shots[0]["url"], f"{self.fake.url}/odoo/sale.order/7")

    def test_any_fail_exit_1(self):
        script_sales(self.fake)
        self.assertEqual(self.ofa_test(PASS_FILE, FAIL_FILE), 1)
        statuses = [s["status"] for s in json.loads(self.read("test.json"))["scenarios"]]
        self.assertEqual(statuses, ["pass", "fail"])

    def test_any_error_exit_4(self):
        script_sales(self.fake)
        self.fake.script("res.partner", "search", [])  # the precondition fails
        self.assertEqual(self.ofa_test(PASS_FILE, FAIL_FILE), 4)

    def test_invalid_scenario_exit_2_before_any_call(self):
        bad = self.plan_dir / "bad.json"
        bad.write_text(json.dumps({"format": "ofa.scenario/1"}))
        self.assertEqual(self.ofa_test(PASS_FILE, bad), 2)
        self.assertIn("BAD_SCENARIO", self.stderr)
        self.assertEqual(self.fake.requests, [])
        self.assertFalse((self.plan_dir / "runs").exists())

    def test_duplicate_scenario_id_exit_2(self):
        self.assertEqual(self.ofa_test(PASS_FILE, PASS_FILE), 2)

    def test_existing_run_dir_and_missing_run(self):
        script_sales(self.fake)
        run = self.plan_dir / "runs" / "20261026T000000Z_t1"
        run.mkdir(parents=True)
        (run / "calls.jsonl").write_text('{"model": "from.apply"}\n')
        self.assertEqual(self.ofa_test(PASS_FILE, run=run.name), 0)
        self.assertEqual(self.stdout.strip(), run.name)
        calls = (run / "calls.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(calls[0]), {"model": "from.apply"})
        self.assertGreater(len(calls), 5)
        self.assertEqual(self.ofa_test(PASS_FILE, run="nope"), 2)


class ArtifactSafetyTest(TestCommandCase):
    def test_calls_jsonl_has_no_key(self):
        script_sales(self.fake)
        self.ofa_test(PASS_FILE)
        text = self.read("calls.jsonl")
        self.assertNotIn(KEY, text)
        self.assertNotIn("bearer", text.lower())
        for line in text.splitlines():
            self.assertEqual(set(json.loads(line)), set(report.CALL_LOG_KEYS))

    def test_no_debug_leak(self):
        script_sales(self.fake)
        boom = Response(500, error_body("odoo.exceptions.UserError", "Cannot confirm", debug=TRACE))
        self.fake.script("sale.order", "action_confirm", boom)
        self.fake.script("sale.order", "read", boom)  # the evidence read-back hits it too
        self.assertEqual(self.ofa_test(PASS_FILE), 1)
        self.assertIn("Cannot confirm", self.read("report.md"))
        self.assertIn("Cannot confirm", self.read("records.json"))
        for name in ("test.json", "records.json", "calls.jsonl", "report.md"):
            text = self.read(name)
            with self.subTest(name=name):
                self.assertNotIn('"debug"', text)
                self.assertNotIn("Traceback", text)
                self.assertNotIn("/home/", text)


class RunDirTest(unittest.TestCase):
    def test_same_second_as_an_earlier_run_waits_for_the_next(self):
        # Seen live: `ofa test` right after `ofa apply` hit the apply's run id and crashed.
        plan_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plan_dir)
        t = [1_793_000_000.4]
        (plan_dir / "runs" / report.new_run_id("t1", t[0])).mkdir(parents=True)
        d = report.run_dir_for(plan_dir, None, "t1", clock=lambda: t[0],
                               sleep=lambda s: t.__setitem__(0, t[0] + s))
        self.assertEqual(d.name, report.new_run_id("t1", 1_793_000_001.0))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp()) / "20261026T000000Z_t1"
        self.run.mkdir()
        self.addCleanup(shutil.rmtree, self.run.parent)

    def test_full_report_uses_relative_links(self):
        report.write_json(self.run / "apply.json", {
            "run_id": self.run.name, "plan_sha256": "cd" * 32, "target": "t1", "db": "ofa_demo_t1",
            "odoo_version": "20.0", "edition": "community", "ops": [
                {"op_id": "op_010", "type": "install_modules", "status": "unchanged", "model": "ir.module.module",
                 "res_ids": [3], "pre_state": True, "error": None, "duration_ms": 1},
                {"op_id": "op_020", "type": "call_method", "status": "failed", "model": "x.y",
                 "res_ids": [], "pre_state": False, "error": "odoo.exceptions.UserError: a | b", "duration_ms": 1}]})
        results = [{"id": "sc_a", "status": "fail", "steps": [
            {"id": "s010", "status": "pass", "message": "", "records": {"model": "m", "ids": [1]}},
            {"id": "s020", "status": "fail", "message": "state of id 1: expected eq \"x\"", "records": {"model": "m", "ids": [1]}}]}]
        records = {"sc_a": {"order": [{"id": 1}], "lines": [{"id": 2}]}}
        shots = [{"scenario": "sc_a", "label": "order", "model": "m", "id": 1, "url": "http://127.0.0.1:8070/odoo/m/1"}]
        (self.run / "screenshots").mkdir()
        (self.run / "screenshots" / "sc_a_order.png").write_bytes(b"png")
        report.write_test_run(self.run, self.run.name, "t1", results, records, shots, [])
        md = (self.run / "report.md").read_text()
        self.assertIn("sha256 `" + "cd" * 32 + "`", md)
        self.assertIn("| op_010 | install_modules | unchanged (pre-state) | ir.module.module | 3 |", md)
        self.assertIn("a \\| b", md)
        self.assertIn("| sc_a | fail | s020 | state of id 1: expected eq \"x\" |", md)
        self.assertIn("- sc_a / order: [records](records.json), [screenshot](screenshots/sc_a_order.png)", md)
        self.assertIn("- sc_a / lines: [records](records.json)", md)
        self.assertNotIn(str(self.run.parent), md)

    def test_bot_group_syncs_are_listed(self):
        op = {"op_id": "op_010", "type": "install_modules", "status": "created", "model": "ir.module.module",
              "res_ids": [3], "pre_state": False, "error": None, "duration_ms": 1}
        report.write_json(self.run / "apply.json", {"run_id": self.run.name, "target": "t1", "ops": [op], "bot_groups": [
            {"at": "start", "added": [], "error": None},
            {"at": "op_010", "added": ["project.group_project_manager", "project.group_project_user"], "error": None}]})
        md = report.render(self.run)
        self.assertIn("- op_010: `project.group_project_manager`, `project.group_project_user`", md)
        self.assertNotIn("- start:", md)

    def test_plan_title_from_plan_dir(self):
        plan_dir = self.run.parent
        (plan_dir / "plan.json").write_text(json.dumps({"title": "My plan"}))
        md = report.render(self.run, plan_dir)
        self.assertIn("- Plan: My plan", md)
        self.assertIn("No apply in this run.", md)
        self.assertIn("No scenarios in this run.", md)


if __name__ == "__main__":
    unittest.main()
