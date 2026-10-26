import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ofa import ROOT, cli
from ofa import plan as planmod
from ofa.errors import ValidationError
from tests.fakeodoo import Response
from tests.unit.test_client import FakeCase

FIXTURES = ROOT / "tests" / "fixtures" / "plans"
SMOKE = FIXTURES / "smoke"


def codes(problems):
    return {p.code for p in problems}


def copy_smoke(testcase):
    tmp = Path(tempfile.mkdtemp())
    testcase.addCleanup(shutil.rmtree, tmp)
    d = tmp / "smoke"
    shutil.copytree(SMOKE, d)
    return d


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class ValidateFixturesTest(unittest.TestCase):
    def test_every_rule_has_a_failing_fixture(self):
        names = {d.name for d in FIXTURES.iterdir() if d.name.startswith("invalid_")}
        self.assertEqual(names, {f"invalid_{c.lower()}" for c in planmod.RULE_CODES})

    def test_each_invalid_fixture_reports_exactly_its_rule(self):
        for code in planmod.RULE_CODES:
            with self.subTest(code=code):
                problems = planmod.validate(FIXTURES / f"invalid_{code.lower()}", target_edition="community")
                self.assertEqual(codes(problems), {code}, [str(p) for p in problems])

    def test_smoke_is_valid_and_uses_all_four_op_types(self):
        self.assertEqual(planmod.validate(SMOKE, target_edition="community"), [])
        plan = planmod.load(SMOKE)
        self.assertEqual({op["type"] for op in plan["operations"]}, set(planmod.OP_TYPES))
        for name in ("requirement.md", "plan.md"):
            self.assertTrue((SMOKE / name).is_file())

    def test_edition_rule_needs_a_community_target(self):
        d = FIXTURES / "invalid_edition_mismatch"
        self.assertEqual(planmod.validate(d), [])
        self.assertEqual(planmod.validate(d, target_edition="enterprise"), [])
        plan = planmod.load(SMOKE)
        plan["edition"] = "enterprise"
        self.assertEqual(codes(planmod.validate(SMOKE, plan, target_edition="community")), {"EDITION_MISMATCH"})

    def test_knowledge_refs_anchor_and_escape(self):
        plan = planmod.load(SMOKE)
        op = plan["operations"][0]
        op["knowledge_refs"] = ["knowledge/20.0/INDEX.md#areas"]
        self.assertEqual(planmod.validate(SMOKE, plan), [])
        for bad in ("../outside.md", "/etc/hostname", "knowledge/20.0", ""):
            op["knowledge_refs"] = [bad]
            self.assertEqual(codes(planmod.validate(SMOKE, plan)), {"MISSING_KNOWLEDGE_REF"}, bad)

    def test_create_is_rejected_anywhere_in_an_op(self):
        plan = planmod.load(SMOKE)
        plan["operations"][4]["params"] = {"lines": {"$create": [{"name": "x"}]}}
        self.assertEqual(codes(planmod.validate(SMOKE, plan)), {"CREATE_NOT_ALLOWED"})

    def test_shape_problems(self):
        plan = planmod.load(SMOKE)
        ops = plan["operations"]
        ops[0]["modules"] = []
        ops[3]["key"] = None
        ops[4]["target"] = 7
        ops[4]["method"] = "_private"
        found = [p for p in planmod.validate(SMOKE, plan) if p.code == "BAD_OP"]
        self.assertEqual({p.op_id for p in found}, {"op_010_install_sales", "op_040_company_mx", "op_050_company_mx_chart"})

    def test_missing_plan_md(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copy(SMOKE / "plan.json", tmp / "plan.json")
        self.assertEqual(codes(planmod.validate(tmp)), {"OP_NOT_IN_PLAN_MD"})

    def test_bad_json(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "plan.json").write_text("{not json")
        with self.assertRaises(ValidationError) as cm:
            planmod.load(tmp)
        self.assertEqual(cm.exception.code, "BAD_JSON")


class OrderTest(unittest.TestCase):
    def test_topological_and_ties_keep_list_order(self):
        def op(i, deps=()):
            return {"id": i, "depends_on": list(deps)}
        plan = {"operations": [op("op_c", ["op_b"]), op("op_a"), op("op_b"), op("op_d", ["op_a"])]}
        self.assertEqual([o["id"] for o in planmod.order(plan)], ["op_a", "op_b", "op_c", "op_d"])

    def test_smoke_order(self):
        ids = [o["id"] for o in planmod.order(planmod.load(SMOKE))]
        self.assertEqual(ids, ["op_010_install_sales", "op_020_line_discounts", "op_030_vip_tag",
                               "op_040_company_mx", "op_050_company_mx_chart"])


class HashTest(unittest.TestCase):
    def test_stable_across_key_order_and_whitespace(self):
        plan = planmod.load(SMOKE)
        sha = planmod.plan_hash(plan)

        def reorder(v):
            if isinstance(v, dict):
                return {k: reorder(v[k]) for k in reversed(list(v))}
            if isinstance(v, list):
                return [reorder(x) for x in v]
            return v

        d = copy_smoke(self)
        (d / "plan.json").write_text(json.dumps(reorder(plan), indent=7, ensure_ascii=False) + "\n\n\n")
        self.assertEqual(planmod.plan_hash(planmod.load(d)), sha)
        (d / "plan.json").write_text(json.dumps(plan, separators=(",", ":")))
        self.assertEqual(planmod.plan_hash(planmod.load(d)), sha)
        plan["operations"][2]["values"]["color"] = 11
        self.assertNotEqual(planmod.plan_hash(plan), sha)

    def test_canonical_form(self):
        self.assertEqual(planmod.canonical_bytes({"b": "ñ", "a": [1, 2]}), '{"a":[1,2],"b":"ñ"}'.encode())


class FreezeTest(unittest.TestCase):
    def test_freeze_writes_hash_and_check_approved(self):
        d = copy_smoke(self)
        plan = planmod.load(d)
        with self.assertRaises(ValidationError) as cm:
            planmod.check_approved(d, plan)
        self.assertEqual(cm.exception.code, "NOT_APPROVED")
        approved = planmod.freeze(d, now=0)
        on_disk = json.loads((d / "plan.approved").read_text())
        self.assertEqual(on_disk, approved)
        self.assertEqual(on_disk, {"sha256": planmod.plan_hash(plan), "approved_at": "1970-01-01T00:00:00Z"})
        self.assertEqual(planmod.check_approved(d, plan), approved["sha256"])
        plan["title"] = "changed"
        with self.assertRaises(ValidationError) as cm:
            planmod.check_approved(d, plan)
        self.assertEqual(cm.exception.code, "HASH_MISMATCH")

    def test_cli_freeze_and_validate(self):
        d = copy_smoke(self)
        code, out, err = run_cli(["validate", str(d)])
        self.assertEqual(code, 0, err)
        self.assertIn("ok: 5 operations", out)
        code, out, _ = run_cli(["freeze", str(d)])
        self.assertEqual(code, 0)
        self.assertIn(planmod.plan_hash(planmod.load(d)), out)

    def test_cli_refuses_invalid_plan(self):
        bad = FIXTURES / "invalid_cycle"
        for cmd in ("validate", "freeze"):
            code, _, err = run_cli([cmd, str(bad)])
            self.assertEqual(code, 2)
            self.assertIn("CYCLE", err)
        self.assertFalse((bad / "plan.approved").exists())


class ApplyRefusalTest(unittest.TestCase):
    def test_unapproved_plan_exits_2_before_any_call(self):
        d = copy_smoke(self)
        with mock.patch("ofa.client.open_client") as opener:
            code, _, err = run_cli(["apply", str(d), "--target", "t1"])
        self.assertEqual(code, 2)
        self.assertIn("NOT_APPROVED", err)
        opener.assert_not_called()
        self.assertFalse((d / "runs").exists())

    def test_modified_plan_exits_2(self):
        d = copy_smoke(self)
        planmod.freeze(d)
        plan = json.loads((d / "plan.json").read_text())
        plan["operations"][1]["values"]["group_discount_per_so_line"] = False
        (d / "plan.json").write_text(json.dumps(plan))
        with mock.patch("ofa.client.open_client") as opener:
            code, _, err = run_cli(["apply", str(d), "--target", "t1"])
        self.assertEqual(code, 2)
        self.assertIn("HASH_MISMATCH", err)
        opener.assert_not_called()


class OnlineCheckTest(FakeCase):
    def test_unresolved_ref_and_plan_keys(self):
        def xmlid(req):
            dom = {t[0]: t[2] for t in req.params["domain"]}
            known = {("base", "main_company"): 1, ("base", "mx"): 156}
            res = known.get((dom["module"], dom["name"]))
            return [{"id": 1, "model": "x", "res_id": res}] if res else []
        self.fake.script("ir.model.data", "search_read", xmlid)
        c = self.open()
        problems = planmod.check_online(c, planmod.load(SMOKE))
        # base.MXN is unknown to this fake; __ofa__.smoke_company_mx is defined by the plan itself.
        self.assertEqual([(p.code, p.op_id, p.message.split()[0]) for p in problems],
                         [("UNRESOLVED_REF", "op_040_company_mx", "base.MXN")])

    def test_validate_cli_with_target_checks_edition(self):
        cfg = self.cfg
        community = cfg.targets["t1"].__class__(**{**cfg.targets["t1"].__dict__, "edition": "community"})
        cfg = cfg.__class__(server=cfg.server, targets={"t1": community})
        self.fake.script("ir.model.data", "search_read", Response(200, [{"id": 1, "model": "x", "res_id": 1}]))
        with mock.patch("ofa.config.load", return_value=cfg):
            code, _, err = run_cli(["validate", str(FIXTURES / "invalid_edition_mismatch"), "--target", "t1"])
            self.assertEqual(code, 2)
            self.assertIn("EDITION_MISMATCH", err)
            code, out, err = run_cli(["validate", str(SMOKE), "--target", "t1"])
            self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
