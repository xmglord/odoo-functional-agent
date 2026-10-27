import copy
import json
import tempfile
import unittest
from pathlib import Path

from ofa import ROOT, scenario
from ofa.errors import ValidationError
from tests.fakeodoo import Response, error_body
from tests.unit.test_client import FakeCase

FIXTURES = ROOT / "tests" / "fixtures" / "scenarios"
PASS_FILE = FIXTURES / "quote_confirm_pass.json"
FAIL_FILE = FIXTURES / "quote_confirm_fail.json"
TRACE = 'Traceback (most recent call last): File "/home/u/x.py"'

SO = {"id": 7, "name": "S00007", "state": "sale", "amount_total": 120.0, "order_line": [71],
      "partner_id": [12, "Demo Partner"], "note": False}


def _xmlid(req):
    d = req.params["domain"]
    if d == [["module", "=", "base"], ["name", "=", "res_partner_12"]]:
        return [{"id": 900, "model": "res.partner", "res_id": 12}]
    return []


def _read(rows):
    def handler(req):
        return [{"id": i, **{f: rows[i].get(f, False) for f in req.params["fields"]}} for i in req.ids if i in rows]
    return handler


def script_sales(fake, so=None, installed=("sale_management",)):
    """Script the calls both scenario fixtures make."""
    fake.script("ir.module.module", "search_read", [{"id": n, "name": m} for n, m in enumerate(installed, 1)])
    fake.script("ir.model.data", "search_read", _xmlid)
    fake.script("res.partner", "search", [12])
    fake.script("product.product", "search", [30])
    fake.script("sale.order", "create", [7])
    fake.script("sale.order", "action_confirm", True)
    fake.script("stock.picking", "search", [40])
    fake.script("stock.picking", "read", _read({40: {"name": "WH/OUT/00001"}}))
    fake.script("sale.order", "read", _read({7: so or SO}))
    fake.script("sale.order", "write", True)


def scenario_dict(path=PASS_FILE):
    return json.loads(Path(path).read_text())


class LoadTest(unittest.TestCase):
    def test_fixtures_are_valid(self):
        for path in (PASS_FILE, FAIL_FILE):
            self.assertEqual(scenario.load(path)["format"], "ofa.scenario/1")

    def test_file_errors(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp))
        bad = tmp / "bad.json"
        bad.write_text("{not json")
        for path in (bad, tmp / "missing.json"):
            with self.assertRaises(ValidationError) as cm:
                scenario.load(path)
            self.assertEqual(cm.exception.code, "BAD_SCENARIO")

    def assertInvalid(self, mutate, needle):
        data = scenario_dict()
        mutate(data)
        with self.assertRaises(ValidationError) as cm:
            scenario.validate(data)
        self.assertEqual(cm.exception.code, "BAD_SCENARIO")
        self.assertIn(needle, cm.exception.msg)

    def test_rules(self):
        def step(i):
            return lambda d: d["steps"][i]
        cases = [
            (lambda d: d.update(format="ofa.scenario/2"), "format"),
            (lambda d: d.pop("description"), "missing description"),
            (lambda d: d.update(extra=1), "unknown key extra"),
            (lambda d: d.update(id="Bad-Id"), "does not match"),
            (lambda d: d.update(area="hr"), "area"),
            (lambda d: d.update(edition="pro"), "edition"),
            (lambda d: d.update(steps=[]), "non-empty list"),
            (lambda d: d["steps"][0].update(action="delete"), "action must be"),
            (lambda d: d["steps"][1].pop("method"), "missing method"),
            (lambda d: d["steps"][1].update(save_as="x"), "unknown key save_as"),
            (lambda d: d["steps"][1].update(id="s010"), "duplicate step id"),
            (lambda d: d["preconditions"][0].update(id="s010"), "duplicate step id"),
            (lambda d: d["steps"][0].update(id="requires"), "reserved"),
            (lambda d: d["steps"][0].update(save_as="1x"), "does not match"),
            (lambda d: d["steps"][2]["expect"].update(fields={"name": {"eq": 1}}), "unknown key fields"),
            (lambda d: d["steps"][4]["expect"]["fields"]["state"].update(like="x"), "unknown operator"),
            (lambda d: d["steps"][4]["expect"]["fields"]["state"].update({"in": "sale"}), "must be a list"),
            (lambda d: d["steps"][4].update(expect={"count": 1}), "assert needs expect.fields"),
            (lambda d: d["steps"][2]["expect"].update(count="1"), "operators"),
            (lambda d: d["steps"][3].update(fields=[]), "fields"),
            (lambda d: d["evidence"][1].update(label="confirmed_order"), "duplicate label"),
            (lambda d: d["evidence"][0].update(screenshot="yes"), "screenshot"),
            (lambda d: d.update(requires={"modules": "sale"}), "requires.modules"),
            (lambda d: d.update(company=4), "company"),
            (lambda d: d["steps"][0].update(company={"$ref": "base.main_company", "$var": "x"}), "company"),
            (lambda d: d["evidence"][0].update(company="base.main_company"), "company"),
        ]
        for mutate, needle in cases:
            with self.subTest(needle=needle):
                self.assertInvalid(mutate, needle)


class OperatorTest(unittest.TestCase):
    def test_every_operator_passes_and_fails(self):
        cases = {
            "eq": ("a", "a", "b"), "ne": ("a", "b", "a"),
            "in": ("a", ["a", "b"], ["c"]), "not_in": ("a", ["c"], ["a"]),
            "gt": (5, 4, 5), "gte": (5, 5, 6), "lt": (5, 6, 5), "lte": (5, 5, 4),
            "contains": ("S00007", "S000", "X"),
        }
        for op, (actual, good, bad) in cases.items():
            with self.subTest(op=op):
                scenario.check_ops({op: good}, actual, "f")
                with self.assertRaises(scenario.StepFailed) as cm:
                    scenario.check_ops({op: bad}, actual, "f")
                self.assertIn(f"expected {op}", str(cm.exception))

    def test_contains_on_lists_and_numbers_on_false(self):
        scenario.check_ops({"contains": [1, 2]}, [1, 2, 3], "f")
        with self.assertRaises(scenario.StepFailed):
            scenario.check_ops({"contains": 9}, [1, 2], "f")
        with self.assertRaises(scenario.StepFailed):
            scenario.check_ops({"gt": 0}, False, "f")  # Odoo's empty value never compares


class RunTest(FakeCase):
    def setUp(self):
        super().setUp()
        self.c = self.open()

    def run_file(self, path=PASS_FILE):
        return scenario.run(self.c, scenario.load(path))

    def test_pass_resolves_refs_and_collects_evidence(self):
        script_sales(self.fake)
        result, evidence, shots = self.run_file()
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual([s["status"] for s in result["steps"]], ["pass"] * 7)
        self.assertEqual([s["id"] for s in result["steps"]], ["p010", "s010", "s020", "s030", "s040", "s050", "s060"])
        # $ref, $search and $create resolved inside create's vals_list; $var in the later calls
        create = self.fake.calls("sale.order", "create")[0]
        self.assertEqual(create.params, {"vals_list": [{
            "partner_id": 12, "order_line": [[0, 0, {"product_id": 30, "product_uom_qty": 2}]]}]})
        self.assertEqual(self.fake.calls("sale.order", "action_confirm")[0].ids, [7])
        self.assertEqual(self.fake.calls("stock.picking", "search")[0].params, {"domain": [["sale_id", "=", 7]]})
        self.assertEqual(self.fake.calls("sale.order", "write")[0].body, {"ids": [7], "vals": {"note": "checked"}})
        asserted = self.fake.calls("sale.order", "read")[1]
        self.assertEqual(sorted(asserted.params["fields"]), ["amount_total", "name", "order_line", "partner_id", "state"])
        self.assertEqual(result["steps"][1]["records"], {"model": "sale.order", "ids": [7]})
        self.assertEqual(result["steps"][3]["records"], {"model": "stock.picking", "ids": [40]})
        self.assertEqual(evidence["confirmed_order"], [{"id": 7, "name": "S00007", "state": "sale", "amount_total": 120.0}])
        self.assertEqual(evidence["deliveries"], [{"id": 40, "name": "WH/OUT/00001"}])
        self.assertEqual(shots, [{"scenario": "quote_confirm_pass", "label": "confirmed_order", "model": "sale.order",
                                  "id": 7, "url": f"{self.fake.url}/odoo/sale.order/7"}])

    def test_first_failure_stops(self):
        script_sales(self.fake)
        result, _, _ = self.run_file(FAIL_FILE)
        self.assertEqual(result["status"], "fail")
        statuses = {s["id"]: s["status"] for s in result["steps"]}
        self.assertEqual(statuses["s050"], "fail")
        self.assertEqual(statuses["s060"], "skipped")
        self.assertIn("state of id 7: expected eq \"done\", got \"sale\"", result["steps"][5]["message"])
        self.assertEqual(self.fake.calls("sale.order", "write"), [])

    def test_precondition_failure_is_error(self):
        script_sales(self.fake)
        self.fake.script("res.partner", "search", [])
        result, evidence, shots = self.run_file()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["steps"][0]["id"], "p010")
        self.assertEqual(result["steps"][0]["status"], "error")
        self.assertTrue(all(s["status"] == "skipped" for s in result["steps"][1:]))
        self.assertEqual(self.fake.calls("sale.order", "create"), [])
        self.assertEqual((evidence, shots), ({}, []))

    def test_missing_module_is_error(self):
        script_sales(self.fake, installed=())
        result, _, _ = self.run_file()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["steps"][0], {"id": "requires", "status": "error",
                                              "message": "modules not installed: sale_management",
                                              "records": {"model": "", "ids": []}})
        self.assertEqual(len(result["steps"]), 8)

    def test_enterprise_scenario_on_community_target(self):
        script_sales(self.fake)
        object.__setattr__(self.c.target, "edition", "community")
        data = scenario.load(PASS_FILE)
        data["edition"] = "enterprise"
        result, _, _ = scenario.run(self.c, data)
        self.assertEqual(result["status"], "error")
        self.assertIn("needs enterprise", result["steps"][0]["message"])

    def test_odoo_error_is_fail_and_message_has_no_debug(self):
        script_sales(self.fake)
        self.fake.script("sale.order", "action_confirm",
                         Response(422, error_body("odoo.exceptions.UserError", "Cannot confirm", debug=TRACE)))
        result, _, _ = self.run_file()
        self.assertEqual(result["status"], "fail")
        step = result["steps"][2]
        self.assertEqual(step["message"], "odoo.exceptions.UserError: Cannot confirm")
        self.assertEqual(step["records"], {"model": "sale.order", "ids": [7]})

    def test_unresolved_ref_is_fail(self):
        script_sales(self.fake)
        self.fake.script("ir.model.data", "search_read", lambda req: [])
        data = copy.deepcopy(scenario.load(PASS_FILE))
        data.pop("preconditions")
        result, _, _ = scenario.run(self.c, data)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["steps"][0]["message"].startswith("UNRESOLVED_REF"))

    def test_server_down_is_error(self):
        script_sales(self.fake)
        self.fake.__exit__(None, None, None)
        result, _, _ = self.run_file()
        self.assertEqual(result["status"], "error")
        self.assertTrue(result["steps"][0]["message"].startswith("SERVER_DOWN"))

    def test_company_context_scenario_step_and_evidence(self):
        # The scenario runs in company 1; s020 overrides it with company 3, and so does the second evidence item.
        script_sales(self.fake)
        self.fake.script("ir.model.data", "search_read", lambda req: (
            [{"id": 901, "model": "res.company", "res_id": 3}]
            if req.params["domain"] == [["module", "=", "__ofa__"], ["name", "=", "sub"]] else _xmlid(req)))
        data = copy.deepcopy(scenario.load(PASS_FILE))
        self.fake.script("res.company", "search", [1])
        data["company"] = {"$search": {"model": "res.company", "domain": [["id", "=", 1]]}}
        data["steps"][1]["company"] = {"$ref": "__ofa__.sub"}
        data["evidence"][1]["company"] = {"$ref": "__ofa__.sub"}
        scenario.validate(data)
        result, evidence, _ = scenario.run(self.c, data)
        self.assertEqual(result["status"], "pass", result)
        ctx = lambda req: (req.context or {}).get("allowed_company_ids")
        self.assertEqual(ctx(self.fake.calls("sale.order", "create")[0]), [1])
        self.assertEqual(ctx(self.fake.calls("sale.order", "action_confirm")[0]), [3])
        self.assertEqual(ctx(self.fake.calls("stock.picking", "search")[0]), [1])
        self.assertEqual(ctx(self.fake.calls("sale.order", "read")[-1]), [1])
        self.assertEqual(ctx(self.fake.calls("stock.picking", "read")[-1]), [3])
        # Without a company nothing sends a context, as before.
        self.fake.requests.clear()
        scenario.run(self.c, scenario.load(PASS_FILE))
        self.assertTrue(all(r.context is None for r in self.fake.requests))

    def test_company_that_does_not_resolve_to_one_id_fails_the_step(self):
        script_sales(self.fake)
        data = copy.deepcopy(scenario.load(PASS_FILE))
        data["steps"][0]["company"] = {"$var": "missing"}
        result, _, _ = scenario.run(self.c, data)
        self.assertEqual(result["steps"][1]["status"], "fail")

    def test_scrub(self):
        self.assertEqual(scenario.scrub('boom ' + TRACE), "boom [traceback removed]")
        self.assertEqual(scenario.scrub("see /home/u/x.py now"), "see <path> now")


if __name__ == "__main__":
    unittest.main()
