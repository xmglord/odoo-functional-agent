import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ofa import ROOT, cli, executor
from ofa import plan as planmod
from ofa.errors import OdooError, ValidationError
from tests.fakeodoo import Response, error_body
from tests.unit.test_client import MARKER, TRACE, FakeCase

SMOKE = ROOT / "tests" / "fixtures" / "plans" / "smoke"
BOT_UID = 7
DB_UUID = "0b7e6f6a-0000-4000-8000-00000000d00d"
MANY2ONE = {"country_id", "currency_id", "parent_id"}


def _match(row, domain):
    for term in domain:
        if not isinstance(term, list):
            continue
        field, op, value = term
        have = row.get(field)
        if op == "=" and have != value:
            return False
        if op == "!=" and have == value:
            return False
        if op == "in" and have not in value:
            return False
    return True


class Sim:
    """A tiny stateful Odoo behind FakeOdoo callables: enough for the smoke plan."""

    def __init__(self, *, sale_installed=False, discounts=False, auto_chart=False):
        self.next_id = 100
        self.auto_chart = auto_chart
        self.settings = {"group_discount_per_so_line": discounts}
        self.tables = {
            "ir.model.data": {
                1: {"module": "base", "name": "main_company", "model": "res.company", "res_id": 1},
                2: {"module": "base", "name": "mx", "model": "res.country", "res_id": 156},
                3: {"module": "base", "name": "MXN", "model": "res.currency", "res_id": 33},
            },
            "ir.module.module": {50: {"name": "sale_management", "state": "installed" if sale_installed else "uninstalled"}},
            "res.partner.category": {},
            "res.company": {1: {"name": "Main", "country_id": 233, "currency_id": 1, "chart_template": "generic_coa"}},
            "res.users": {BOT_UID: {"login": "ofa_bot", "company_ids": [1]}},
            "res.config.settings": {},
        }
        self.calls = []

    def _new(self, model, vals):
        self.next_id += 1
        row = dict(vals)
        if model == "res.company" and self.auto_chart and row.get("country_id") == 156:
            row["chart_template"] = "mx"  # S2 F2: creating an MX company loads the mx chart
        if model == "res.config.settings":
            row = {**self.settings, **vals}
        self.tables[model][self.next_id] = row
        return self.next_id

    def _apply_vals(self, row, vals):
        for k, v in vals.items():
            if isinstance(v, list) and v and isinstance(v[0], list):
                ids = set(row.get(k) or [])
                for cmd in v:
                    if cmd[0] == 4:
                        ids.add(cmd[1])
                    elif cmd[0] == 6:
                        ids = set(cmd[2])
                row[k] = sorted(ids)
            else:
                row[k] = v

    def _out(self, field, v):
        if field in MANY2ONE:
            return [v, f"name {v}"] if v else False
        return v if v is not None else False

    def handle(self, model, method, req):
        self.calls.append((model, method, req.ids, req.params, req.context))
        p, table = req.params, self.tables.get(model)
        if method == "search_read":
            rows = [(i, r) for i, r in table.items() if _match(r, p["domain"])]
            return [{"id": i, **{f: self._out(f, r.get(f)) for f in p["fields"]}} for i, r in rows]
        if method == "search":
            ids = [i for i, r in table.items() if _match(r, p["domain"])]
            return ids[:p["limit"]] if p.get("limit") else ids
        if method == "search_count":
            return len([i for i, r in table.items() if _match({"id": i, **r}, p["domain"])])
        if method == "read":
            return [{"id": i, **{f: self._out(f, table[i].get(f)) for f in p["fields"]}} for i in req.ids if i in table]
        if method == "write":
            for i in req.ids:
                self._apply_vals(table[i], p["vals"])
            return True
        if method == "create":
            return [self._new(model, vals) for vals in p["vals_list"]]
        if (model, method) == ("ir.module.module", "button_immediate_install"):
            for i in req.ids:
                table[i]["state"] = "installed"
            return {"type": "ir.actions.client", "tag": "reload"}
        if (model, method) == ("res.config.settings", "execute"):
            for i in req.ids:
                self.settings.update({k: v for k, v in table[i].items() if k in self.settings})
            return {"type": "ir.actions.client", "tag": "reload"}
        if (model, method) == ("res.company", "install_l10n_modules"):
            for i in req.ids:
                table[i]["chart_template"] = "mx"
            return True
        raise AssertionError(f"unexpected {model}/{method}")

    def install(self, fake):
        def get_str(req):
            return {"ofa.demo_marker": MARKER, "database.uuid": DB_UUID}.get(req.params["key"], "")
        fake.script("ir.config_parameter", "get_str", get_str)
        methods = ("search_read", "search", "search_count", "read", "write", "create")
        for model in self.tables:
            for method in methods:
                fake.script(model, method, lambda req, m=model, f=method: self.handle(m, f, req))
        for model, method in (("ir.module.module", "button_immediate_install"), ("res.config.settings", "execute"),
                              ("res.company", "install_l10n_modules")):
            fake.script(model, method, lambda req, m=model, f=method: self.handle(m, f, req))


class Clock:
    def __init__(self, t=1_793_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class ExecutorCase(FakeCase):
    def setUp(self):
        super().setUp()
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        self.plan_dir = tmp / "smoke"
        shutil.copytree(SMOKE, self.plan_dir)
        self.plan = planmod.load(self.plan_dir)
        self.clock = Clock()

    def sim(self, **kw):
        sim = Sim(**kw)
        sim.install(self.fake)
        return sim

    def apply(self, plan=None):
        record = executor.run(self.open(), plan or self.plan, self.plan_dir, "abc123", clock=self.clock, sleep=self.clock.sleep)
        self.clock.t += 5
        return record

    def statuses(self, record):
        return {op["op_id"]: op["status"] for op in record["ops"]}


class ExecutorTest(ExecutorCase):
    def test_fresh_apply_then_reapply_is_unchanged(self):
        sim = self.sim()
        first = self.apply()
        self.assertEqual(self.statuses(first), {
            "op_010_install_sales": "created", "op_020_line_discounts": "updated", "op_030_vip_tag": "created",
            "op_040_company_mx": "created", "op_050_company_mx_chart": "called"})
        self.assertFalse(any(op["pre_state"] for op in first["ops"]))
        self.assertEqual(sim.tables["ir.module.module"][50]["state"], "installed")
        self.assertTrue(sim.settings["group_discount_per_so_line"])
        xmlids = {r["name"]: (r["model"], r["res_id"]) for r in sim.tables["ir.model.data"].values() if r["module"] == "__ofa__"}
        self.assertEqual(set(xmlids), {"smoke_vip_tag", "smoke_company_mx"})
        company_id = xmlids["smoke_company_mx"][1]
        self.assertEqual(sim.tables["res.company"][company_id]["chart_template"], "mx")

        second = self.apply()
        self.assertEqual(set(self.statuses(second).values()), {"unchanged"})
        self.assertFalse(any(op["pre_state"] for op in second["ops"]))
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(len([r for r in sim.tables["res.company"]]), 2)

    def test_apply_json_shape(self):
        self.sim()
        rec = self.apply()
        on_disk = json.loads((self.plan_dir / "runs" / rec["run_id"] / "apply.json").read_text())
        self.assertEqual(on_disk, rec)
        self.assertTrue({"run_id", "plan_sha256", "target", "db", "odoo_version", "edition", "started_at",
                         "finished_at", "ops"} <= set(rec))
        self.assertRegex(rec["run_id"], r"^\d{8}T\d{6}Z_t1$")
        self.assertEqual((rec["plan_sha256"], rec["target"], rec["db"]), ("abc123", "t1", "ofa_demo_t1"))
        for op in rec["ops"]:
            self.assertEqual(set(op), {"op_id", "type", "status", "model", "res_ids", "pre_state", "error", "duration_ms"})
        self.assertEqual(rec["ops"][0]["model"], "ir.module.module")

    def test_new_company_is_granted_to_the_bot(self):
        sim = self.sim()
        self.apply()
        company_id = max(sim.tables["res.company"])
        self.assertIn(company_id, sim.tables["res.users"][BOT_UID]["company_ids"])
        grant = [c for c in sim.calls if c[:2] == ("res.users", "write")]
        self.assertEqual(grant, [("res.users", "write", [BOT_UID], {"vals": {"company_ids": [[4, company_id]]}}, None)])
        # A re-apply does not grant again.
        self.apply()
        self.assertEqual(len([c for c in sim.calls if c[:2] == ("res.users", "write")]), 1)

    def test_pre_state_on_first_apply_only(self):
        self.sim(sale_installed=True, discounts=True, auto_chart=True)
        first = self.apply()
        self.assertEqual(self.statuses(first), {
            "op_010_install_sales": "unchanged", "op_020_line_discounts": "unchanged", "op_030_vip_tag": "created",
            "op_040_company_mx": "created", "op_050_company_mx_chart": "unchanged"})
        pre = {op["op_id"] for op in first["ops"] if op["pre_state"]}
        # op_050 is unchanged only because op_040 created the company in this run.
        self.assertEqual(pre, {"op_010_install_sales", "op_020_line_discounts"})
        second = self.apply()
        self.assertFalse(any(op["pre_state"] for op in second["ops"]))

    def test_unchanged_on_a_record_this_run_created_is_not_pre_state(self):
        # The live smoke shape: op_040 creates the MX company (whose creation loads the chart),
        # so op_050's skip_if holds, but because of this plan, not because of the template.
        self.sim(auto_chart=True)
        rec = self.apply()
        ops = {op["op_id"]: op for op in rec["ops"]}
        self.assertEqual(ops["op_040_company_mx"]["status"], "created")
        self.assertEqual((ops["op_050_company_mx_chart"]["status"], ops["op_050_company_mx_chart"]["pre_state"]),
                         ("unchanged", False))
        self.assertEqual(executor.produced_in_run(self.plan, rec), {"op_050_company_mx_chart"})

    def test_adopted_record_also_counts_as_produced(self):
        sim = self.sim(auto_chart=True)
        sim.tables["res.company"][80] = {"name": "Smoke Demo MX SA de CV", "country_id": 156, "currency_id": 33,
                                         "chart_template": "mx"}
        rec = self.apply()
        self.assertEqual(rec["ops"][3]["status"], "adopted")
        self.assertFalse(rec["ops"][4]["pre_state"])

    def test_independent_unchanged_op_keeps_pre_state(self):
        self.sim(sale_installed=True, auto_chart=True)
        rec = self.apply()
        op = rec["ops"][0]
        self.assertEqual((op["op_id"], op["status"], op["pre_state"]), ("op_010_install_sales", "unchanged", True))
        self.assertNotIn("op_010_install_sales", executor.produced_in_run(self.plan, rec))

    def test_chained_refs_carry_the_dependency(self):
        state = executor.RunState()
        a = {"id": "op_a", "type": "upsert_record", "key": "a"}
        b = {"id": "op_b", "type": "upsert_record", "key": "b", "values": {"parent_id": {"$ref": "__ofa__.a"}}}
        c = {"id": "op_c", "type": "call_method", "target": {"$ref": "__ofa__.b"}}
        d = {"id": "op_d", "type": "call_method", "target": {"$ref": "base.main_company"}}
        self.assertFalse(state.record(a, "created"))
        self.assertTrue(state.record(b, "unchanged"))   # b itself unchanged, but it hangs off a
        self.assertTrue(state.record(c, "unchanged"))   # through b
        self.assertFalse(state.record(d, "unchanged"))

    def test_reset_db_counts_as_fresh(self):
        self.sim(sale_installed=True, discounts=True)
        self.apply()
        # A reset DB: fresh state and a regenerated database.uuid, same name.
        self.sim(sale_installed=True, discounts=True)
        self.fake.script("ir.config_parameter", "get_str",
                         lambda req: MARKER if req.params["key"] == "ofa.demo_marker" else "another-uuid")
        rec = self.apply()
        self.assertTrue(rec["ops"][0]["pre_state"])

    def test_updated_writes_only_the_diff(self):
        sim = self.sim()
        self.apply()
        tag_id = next(iter(sim.tables["res.partner.category"]))
        sim.tables["res.partner.category"][tag_id]["color"] = 3
        rec = self.apply()
        self.assertEqual(self.statuses(rec)["op_030_vip_tag"], "updated")
        writes = [c for c in sim.calls if c[:2] == ("res.partner.category", "write")]
        self.assertEqual(writes[-1][2:4], ([tag_id], {"vals": {"color": 10}}))
        self.assertEqual(sim.tables["res.partner.category"][tag_id]["color"], 10)

    def test_adopted_record_found_by_match(self):
        sim = self.sim()
        sim.tables["res.partner.category"][90] = {"name": "Smoke VIP", "color": 2}
        rec = self.apply()
        op = rec["ops"][2]
        self.assertEqual((op["status"], op["res_ids"]), ("adopted", [90]))
        self.assertEqual(sim.tables["res.partner.category"][90]["color"], 10)
        self.assertIn({"module": "__ofa__", "name": "smoke_vip_tag", "model": "res.partner.category", "res_id": 90},
                      list(sim.tables["ir.model.data"].values()))
        self.assertEqual(len(sim.tables["res.partner.category"]), 1)
        self.assertEqual(self.statuses(self.apply())["op_030_vip_tag"], "unchanged")

    def test_match_not_unique_fails(self):
        sim = self.sim()
        sim.tables["res.partner.category"].update({90: {"name": "Smoke VIP"}, 91: {"name": "Smoke VIP"}})
        rec = self.apply()
        self.assertEqual(rec["ops"][2]["status"], "failed")
        self.assertTrue(rec["ops"][2]["error"].startswith("MATCH_NOT_UNIQUE: "))

    def test_company_context_on_settings_calls(self):
        sim = self.sim()
        self.apply()
        ctxs = [c[4] for c in sim.calls if c[0] == "res.config.settings"]
        self.assertTrue(ctxs)
        self.assertTrue(all(ctx == {"allowed_company_ids": [1]} for ctx in ctxs))
        self.assertTrue(all(c[4] is None for c in sim.calls if c[0] == "res.partner.category"))

    def test_failure_stops_the_run_and_error_is_clean(self):
        sim = self.sim()
        self.fake.script("res.company", "create", Response(500, error_body(
            "odoo.exceptions.ValidationError", "The company name must be unique", debug=TRACE)))
        rec = self.apply()
        self.assertEqual(self.statuses(rec), {
            "op_010_install_sales": "created", "op_020_line_discounts": "updated", "op_030_vip_tag": "created",
            "op_040_company_mx": "failed", "op_050_company_mx_chart": "skipped"})
        self.assertEqual(rec["ops"][3]["error"], "odoo.exceptions.ValidationError: The company name must be unique")
        self.assertIsNone(rec["ops"][4]["error"])
        text = (self.plan_dir / "runs" / rec["run_id"] / "apply.json").read_text()
        self.assertNotIn("Traceback", text)
        self.assertNotIn("/home/", text)
        self.assertNotIn("debug", text)
        self.assertTrue(executor.has_failure(rec))
        self.assertFalse(any(c[:2] == ("res.company", "install_l10n_modules") for c in sim.calls))

    def test_unhandled_wizard_fails_the_op(self):
        self.sim()
        self.fake.script("res.company", "install_l10n_modules", {
            "type": "ir.actions.act_window", "target": "new", "res_model": "some.wizard", "res_id": 3})
        rec = self.apply()
        self.assertEqual(rec["ops"][4]["status"], "failed")
        self.assertEqual(rec["ops"][4]["error"], "UNHANDLED_WIZARD: some.wizard")

    def test_unknown_module_fails(self):
        self.sim()
        self.plan["operations"][0]["modules"] = ["sale_management", "no_such_module"]
        rec = self.apply()
        self.assertEqual(rec["ops"][0]["status"], "failed")
        self.assertIn("no_such_module", rec["ops"][0]["error"])
        self.assertEqual({op["status"] for op in rec["ops"][1:]}, {"skipped"})

    def test_run_id_collision_waits_for_the_next_second(self):
        self.sim()
        a = executor.run(self.open(), self.plan, self.plan_dir, "x", clock=self.clock, sleep=self.clock.sleep)
        b = executor.run(self.open(), self.plan, self.plan_dir, "x", clock=self.clock, sleep=self.clock.sleep)
        self.assertNotEqual(a["run_id"], b["run_id"])


class SafeErrorTest(unittest.TestCase):
    def test_strips_traceback_and_paths(self):
        e = OdooError(500, "odoo.exceptions.UserError", "bad value\n" + TRACE)
        self.assertEqual(executor.safe_error(e), "odoo.exceptions.UserError: bad value")
        e = OdooError(500, "builtins.FileNotFoundError", "no file /home/someone/odoo/data/x.txt here")
        self.assertEqual(executor.safe_error(e), "builtins.FileNotFoundError: no file <path> here")
        e = OdooError(502, "", "<html>bad gateway</html>")
        self.assertEqual(executor.safe_error(e), "HTTP 502: <html>bad gateway</html>")
        self.assertEqual(executor.safe_error(ValidationError("UNRESOLVED_REF", "base.xx does not exist")),
                         "UNRESOLVED_REF: base.xx does not exist")

    def test_keeps_urls(self):
        e = OdooError(0, "SERVER_DOWN", "http://127.0.0.1:8070/json/2 not answering")
        self.assertIn("http://127.0.0.1:8070/json/2", executor.safe_error(e))


class ApplyCliTest(ExecutorCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("ofa.config.load", return_value=self.cfg), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_apply_prints_run_id_and_exit_codes(self):
        self.sim()
        planmod.freeze(self.plan_dir)
        code, out, err = self.run_cli(["apply", str(self.plan_dir), "--target", "t1"])
        self.assertEqual(code, 0, err)
        run_id = out.strip()
        self.assertTrue((self.plan_dir / "runs" / run_id / "apply.json").is_file())
        self.assertIn("op_040_company_mx: created", err)

    def test_apply_output_names_state_produced_in_run(self):
        self.sim(sale_installed=True, auto_chart=True)
        planmod.freeze(self.plan_dir)
        code, _, err = self.run_cli(["apply", str(self.plan_dir), "--target", "t1"])
        self.assertEqual(code, 0, err)
        self.assertIn("op_050_company_mx_chart: unchanged (state produced earlier in this run)", err)
        self.assertIn("op_010_install_sales: unchanged (pre_state: already true before this plan)", err)
        self.assertNotIn("op_050_company_mx_chart: unchanged (pre_state", err)

    def test_apply_exit_1_on_failed_op(self):
        self.sim()
        self.fake.script("res.company", "create", Response(500, error_body("odoo.exceptions.ValidationError", "dup", debug=TRACE)))
        planmod.freeze(self.plan_dir)
        code, out, err = self.run_cli(["apply", str(self.plan_dir), "--target", "t1"])
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", out + err)
        self.assertIn("op_050_company_mx_chart: skipped", err)


if __name__ == "__main__":
    unittest.main()
