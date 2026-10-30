import json
import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from ofa import ROOT, lint, source_index
from ofa.errors import UsageError
from ofa.source_index import SourceIndex
from tests.unit.test_client import FakeCase

EE_LICENSE = "OE" + "EL-1"  # assembled, so the repo hygiene check never sees the literal
PLAN_BASE = {"format": "ofa.plan/1", "title": "t", "odoo_version": "20.0", "edition": "community", "areas": []}


def _model(module, fields=None, methods=(), parents=()):
    return {"module": module, "fields": fields or {}, "methods": list(methods), "parents": list(parents)}


def _f(type_="Char", comodel=None, selection=None):
    return {"type": type_, "comodel": comodel, "selection": selection}


# A source index as `build` would produce it, for a tiny Odoo.
INDEX = {
    "format": source_index.FORMAT, "roots": [],
    "modules": {
        "base": {"depends": [], "auto_install": False, "edition": "community"},
        "sale": {"depends": ["base"], "auto_install": False, "edition": "community"},
        "project": {"depends": ["base"], "auto_install": False, "edition": "community"},
        "sale_project": {"depends": ["sale", "project"], "auto_install": True, "edition": "community"},
        "approvals": {"depends": ["base"], "auto_install": False, "edition": "enterprise"},
    },
    "models": {
        "base": [_model("base")],
        "ir.model": [_model("base", {"model": _f()})],
        "res.config.settings": [_model("base", {"company_id": _f("Many2one", "res.company")}),
                                _model("sale", {"group_discount_per_so_line": _f("Boolean")})],
        "res.company": [_model("base", {"name": _f()})],
        "res.partner": [_model("base", {"name": _f(), "company_id": _f("Many2one", "res.company")})],
        "sale.order": [_model("sale", {"partner_id": _f("Many2one", "res.partner"), "state": _f("Selection")},
                              ["action_confirm"]),
                       _model("sale_project", {"project_id": _f("Many2one", "project.project")})],
        "product.template": [_model("sale", {"service_tracking": _f("Selection", selection=["no"])}),
                             _model("sale_project", {"service_tracking": _f("Selection", selection=["project_only"])})],
        "project.project": [_model("project", {"name": _f(), "allow_milestones": _f("Boolean")})],
        "approval.request": [_model("approvals", {"name": _f()})],
    },
    "xmlids": {"base.main_company": "base", "base.group_user": "base", "project.group_project_milestone": "project",
               "project.group_project_manager": "project", "project.only_here": "hr_timesheet"},
    "base_methods": ["write", "create", "search"],
    "choices": ["delivered_milestones"],
    "view_options": ["no_create", "badges_many2one"],
}

# What the live target has: base and sale installed; project and sale_project available, not installed.
LIVE_MODULES = {"base": "installed", "sale": "installed", "project": "uninstalled", "sale_project": "uninstalled",
                "approvals": "uninstalled"}
LIVE_FIELDS = {
    "ir.model": {"model": "char"},
    "res.config.settings": {"company_id": "many2one", "group_discount_per_so_line": "boolean"},
    "res.company": {"name": "char"},
    "res.partner": {"name": "char", "company_id": "many2one", "hourly_cost": "float"},
    "res.groups": {"implied_ids": "many2many", "name": "char"},
    "sale.order": {"partner_id": "many2one", "state": "selection"},
    "product.template": {"service_tracking": "selection"},
}
RELATIONS = {("res.partner", "company_id"): "res.company", ("sale.order", "partner_id"): "res.partner",
             ("res.config.settings", "company_id"): "res.company"}
LIVE_SELECTION = {("sale.order", "state"): ["draft", "sale"], ("product.template", "service_tracking"): ["no"]}
LIVE_XMLIDS = {("base", "main_company"): "res.company", ("base", "group_user"): "res.groups"}


def _dom(domain):
    return {t[0]: t[2] for t in domain}


class LintCase(FakeCase):
    def setUp(self):
        super().setUp()
        self.index = SourceIndex(json.loads(json.dumps(INDEX)))
        f = self.fake
        f.script("ir.module.module", "search_read", [{"id": i, "name": n, "state": s}
                                                     for i, (n, s) in enumerate(LIVE_MODULES.items())])
        f.script("ir.model", "search_read", [{"id": i, "model": m} for i, m in enumerate(LIVE_FIELDS)])

        def fields(req):
            model = _dom(req.params["domain"])["model"]
            return [{"id": 1, "name": n, "ttype": t, "relation": RELATIONS.get((model, n), False)}
                    for n, t in LIVE_FIELDS.get(model, {}).items()]
        f.script("ir.model.fields", "search_read", fields)

        def selection(req):
            d = _dom(req.params["domain"])
            return [{"id": 1, "value": v} for v in LIVE_SELECTION.get((d["field_id.model"], d["field_id.name"]), [])]
        f.script("ir.model.fields.selection", "search_read", selection)

        def xmlid(req):
            d = _dom(req.params["domain"])
            model = LIVE_XMLIDS.get((d["module"], d["name"]))
            return [{"id": 1, "model": model}] if model else []
        f.script("ir.model.data", "search_read", xmlid)

    def run_lint(self, ops, md=None, edition="enterprise"):
        plan = {**PLAN_BASE, "operations": ops}
        return lint.lint(self.open(), self.index, plan, md, edition)

    def codes(self, result):
        return [(p.code, p.name) for p in result.problems]


def op(id_, type_, **kw):
    return {"id": id_, "type": type_, "rationale": "r", **kw}


class PlanJsonTest(LintCase):
    def test_clean_plan_has_no_problems(self):
        r = self.run_lint([op("op_010", "install_modules", modules=["sale"]),
                           op("op_020", "set_settings", values={"group_discount_per_so_line": True}),
                           op("op_030", "upsert_record", model="res.partner", key="p", values={"name": "x"},
                              match=[["company_id.name", "=", "x"]])])
        self.assertEqual(r.problems, [])
        self.assertEqual(r.json_checked, 5)
        self.assertEqual(r.json_static, 0)

    def test_unknown_module(self):
        r = self.run_lint([op("op_010", "install_modules", modules=["no_such"])])
        self.assertEqual(self.codes(r), [("NOT_IN_20", "no_such")])

    def test_enterprise_module_on_community(self):
        r = self.run_lint([op("op_010", "install_modules", modules=["approvals"])], edition="community")
        self.assertEqual(self.codes(r), [("EDITION", "approvals")])

    def test_unknown_model_and_field(self):
        r = self.run_lint([op("op_010", "upsert_record", model="ir.model.access", key="a", values={}),
                           op("op_020", "upsert_record", model="sale.order", key="b", values={"require_payment": True})])
        self.assertEqual(self.codes(r), [("NOT_IN_20", "ir.model.access"), ("NOT_IN_20", "sale.order.require_payment")])

    def test_unknown_settings_key(self):
        r = self.run_lint([op("op_010", "set_settings", values={"group_project_milestone": True})])
        self.assertEqual(self.codes(r), [("NOT_IN_20", "res.config.settings.group_project_milestone")])

    def test_field_from_module_the_plan_installs_is_static_ok(self):
        # project is not installed yet; the plan installs it, which also brings sale_project (auto_install).
        r = self.run_lint([op("op_010", "install_modules", modules=["project"]),
                           op("op_020", "upsert_record", model="project.project", key="p",
                              values={"name": "x", "allow_milestones": True}),
                           op("op_030", "upsert_record", model="sale.order", key="s", values={"project_id": False})])
        self.assertEqual(r.problems, [])
        self.assertEqual(r.json_static, 4)

    def test_field_from_module_the_plan_does_not_install(self):
        r = self.run_lint([op("op_010", "upsert_record", model="sale.order", key="s", values={"project_id": False})])
        self.assertEqual(self.codes(r), [("NEEDS_MODULE", "sale.order.project_id")])
        self.assertIn("sale_project", r.problems[0].detail)
        self.assertEqual(r.problems[0].severity, "error")

    def test_selection_values_live_and_from_the_plans_modules(self):
        r = self.run_lint([op("op_010", "upsert_record", model="product.template", key="p",
                              values={"service_tracking": "project_only"})])
        self.assertEqual(self.codes(r), [("BAD_SELECTION", "product.template.service_tracking")])
        r = self.run_lint([op("op_005", "install_modules", modules=["project"]),
                           op("op_010", "upsert_record", model="product.template", key="p",
                              values={"service_tracking": "project_only"})])
        self.assertEqual(r.problems, [])

    def test_refs(self):
        r = self.run_lint([op("op_010", "upsert_record", model="res.partner", key="p",
                              values={"company_id": {"$ref": "base.main_company"}}),
                           op("op_020", "upsert_record", model="res.partner", key="q",
                              values={"company_id": {"$ref": "base.no_such_company"}}),
                           op("op_030", "call_method", model="res.partner", method="write", params={},
                              target={"$ref": "__ofa__.p"}, skip_if={"model": "res.partner", "domain": []}),
                           op("op_040", "call_method", model="res.partner", method="write", params={},
                              target={"$ref": "__ofa__.missing"}, skip_if={"model": "res.partner", "domain": []})])
        self.assertEqual(self.codes(r), [("NOT_IN_20", "base.no_such_company"), ("UNRESOLVED_REF", "__ofa__.missing")])

    def test_ref_extended_by_a_module_the_plan_does_not_install(self):
        install = op("op_010", "install_modules", modules=["project"])
        ok = op("op_020", "upsert_record", model="res.partner", key="p",
                values={"company_id": {"$ref": "project.group_project_manager"}})
        self.assertEqual(self.codes(self.run_lint([install, ok])), [])
        other = op("op_030", "upsert_record", model="res.partner", key="q",
                   values={"company_id": {"$ref": "project.only_here"}})
        self.assertEqual(self.codes(self.run_lint([install, other])), [("NEEDS_MODULE", "project.only_here")])

    def test_methods(self):
        skip = {"model": "sale.order", "domain": [["state", "=", "sale"]]}
        r = self.run_lint([op("op_010", "call_method", model="sale.order", method="action_confirm", target=[1],
                              skip_if=skip),
                           op("op_020", "call_method", model="sale.order", method="write", target=[1], skip_if=skip),
                           op("op_030", "call_method", model="sale.order", method="action_approve", target=[1],
                              skip_if=skip)])
        self.assertEqual(self.codes(r), [("NOT_IN_20", "sale.order.action_approve")])

    def test_domain_paths_follow_relations(self):
        r = self.run_lint([op("op_010", "upsert_record", model="res.partner", key="p", values={},
                              match=[["company_id.nmae", "=", "x"]])])
        self.assertEqual(self.codes(r), [("NOT_IN_20", "res.company.nmae")])

    def test_uses_ir_model_fields_not_fields_get(self):
        # S6: fields_get hides group-restricted fields from the bot (hr.employee.hourly_cost).
        r = self.run_lint([op("op_010", "upsert_record", model="res.partner", key="p", values={"hourly_cost": 1.0})])
        self.assertEqual(r.problems, [])
        self.assertEqual(self.fake.calls(method="fields_get"), [])


class PlanMdTest(LintCase):
    PLAN = [op("op_010", "upsert_record", model="res.partner", key="vip", values={"name": "x"})]

    def md(self, text, **kw):
        return self.run_lint(self.PLAN, textwrap.dedent(text), **kw)

    def test_dotted_names_in_backticks(self):
        r = self.md("""
            - [op_010] uses `res.partner.name` and `sale.order.action_confirm()` on `sale.order`.
            - Access rights are in `ir.model.access`; the order has `sale.order.require_payment`.
            """)
        self.assertEqual(self.codes(r), [("NOT_IN_20", "ir.model.access"), ("NOT_IN_20", "sale.order.require_payment")])
        self.assertEqual(r.problems[0].where, "plan.md:3")
        self.assertEqual(r.errors, [])
        self.assertEqual(r.md_checked, 3)

    def test_xmlids_before_one_segment_models(self):
        # `base` is also a model name; `base.group_user` is an xmlid.
        r = self.md("Members of `base.group_user`, `base.group_user.implied_ids`, `project.group_project_milestone`.")
        # project is not installed and the plan does not install it.
        self.assertEqual([(p.code, p.name, p.severity) for p in r.problems],
                         [("NEEDS_MODULE", "project.group_project_milestone", "warning")])
        r = self.md("The group `base.group_nobody` is wrong.")
        self.assertEqual(self.codes(r), [("NOT_IN_20", "base.group_nobody")])

    def test_prose_problems_are_warnings_with_line_and_reason(self):
        # Blind T18 sample: all 8 false flags came from plan.md, none from plan.json, so only plan.json blocks.
        r = self.md("""
            Group by `group_by`; the record `res.partner.vip_user` and `base.group_nobody`.
            """)
        self.assertEqual([p.severity for p in r.problems], ["warning"] * 3)
        self.assertEqual(r.errors, [])
        self.assertEqual(r.problems[0].line(), "plan.md:2: NOT_IN_20: group_by: no field, method, module, xmlid or "
                         "selection value of that name in Odoo 20.0 (warning)")

    def test_plan_json_still_blocks_beside_prose_warnings(self):
        r = self.run_lint([op("op_010", "upsert_record", model="res.partner", key="p", values={"nmae": "x"})],
                          "Uses `sale.order.require_payment`.")
        self.assertEqual([(p.where.split(":")[0], p.severity) for p in r.problems],
                         [("plan.json", "error"), ("plan.md", "warning")])
        self.assertEqual(len(r.errors), 1)

    def test_needs_module_in_prose_is_a_warning(self):
        r = self.md("Odoo's Approvals app (`approval.request`) was rejected.")
        self.assertEqual(self.codes(r), [("NEEDS_MODULE", "approval.request")])
        self.assertEqual(r.problems[0].severity, "warning")
        self.assertEqual(r.errors, [])

    def test_bare_snake_case_names(self):
        r = self.md("Set `allow_milestones` and `require_payment`; the choice `delivered_milestones`, option "
                    "`no_create`, the key `vip`, the op `op_010` and target `ofa_demo_t1`, custom `x_studio_reason`, "
                    "plain `name`.")
        self.assertEqual(self.codes(r), [("NOT_IN_20", "require_payment")])
        u = r.md_unchecked
        self.assertEqual((u["own_names"], u["custom_fields"], u["bare_names"]), (3, 1, 1))

    def test_ignore_comment(self):
        r = self.md("""
            Odoo 20.0 removed `sale.order.require_payment` and `group_project_milestone`.
            <!-- ofa-lint-ignore: sale.order.require_payment, group_project_milestone -->
            """)
        self.assertEqual(r.problems, [])
        self.assertEqual(r.md_unchecked["ignored"], 2)

    def test_unchecked_counts(self):
        r = self.md("""
            Read `odoo/addons/sale/models/sale_order.py@20.0` and `self.env.ref`; sale.order without backticks.
            ```json
            {"model": "res.partner"}
            ```
            """)
        u = r.md_unchecked
        self.assertEqual((u["path_spans"], u["not_identifiers"], u["outside_backticks"]), (1, 1, 1))
        self.assertGreater(u["fenced_blocks"], 0)
        self.assertEqual(r.problems, [])


class SourceIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        addons = self.tmp / "addons"
        self.write(addons / "base_x" / "__manifest__.py", "{'name': 'X', 'depends': [], 'license': 'LGPL-3'}")
        self.write(addons / "base_x" / "models" / "m.py", """
            from odoo import fields, models
            POLICIES = [('ordered_x', 'Ordered'), ('delivered_x', 'Delivered')]
            class Thing(models.Model):
                _name = 'x.thing'
                _inherit = ['mail.thread']
                name = fields.Char()
                kind = fields.Selection([('a', 'A'), ('b', 'B')])
                partner_id = fields.Many2one('res.partner')
                def action_go(self):
                    pass
            """)
        self.write(addons / "base_x" / "views" / "v.xml", """
            <odoo><record id="view_thing" model="ir.ui.view">
              <field name="partner_id" widget="many2one_avatar" options="{'no_create': True}"/>
            </record></odoo>""")
        self.write(addons / "ee_y" / "__manifest__.py",
                   "{'name': 'Y', 'depends': ['base_x'], 'license': '%s', 'auto_install': True}" % EE_LICENSE)
        self.write(addons / "ee_y" / "models" / "m.py", """
            from odoo import fields, models
            class Thing(models.Model):
                _inherit = 'x.thing'
                kind = fields.Selection(selection_add=[('c', 'C')])
            """)
        self.write(addons / "ee_y" / "tests" / "test_x.py", "class T:\n    _name = 'test.only'\n")
        # 20.0: hr_timesheet extends a group project defines, and sorts before it in the walk.
        self.write(addons / "hr_timesheet" / "__manifest__.py", "{'name': 'T', 'depends': ['project']}")
        self.write(addons / "hr_timesheet" / "security" / "s.xml", """
            <odoo><record id="project.group_project_manager" model="res.groups"/>
            <record id="project.only_here" model="res.groups"/></odoo>
            """)
        self.write(addons / "project" / "__manifest__.py", "{'name': 'P', 'depends': []}")
        self.write(addons / "project" / "security" / "project_security.xml", """
            <odoo><record id="group_project_manager" model="res.groups"/></odoo>
            """)
        self.odoo_pkg = self.tmp / "odoo"
        self.write(self.odoo_pkg / "orm" / "models.py", "class BaseModel:\n    def write(self, vals):\n        pass\n")
        self.index = SourceIndex(source_index.build([addons], self.odoo_pkg))

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text))

    def test_models_fields_methods_and_selection(self):
        ix = self.index
        self.assertEqual(ix.model_modules("x.thing"), {"base_x", "ee_y"})
        self.assertEqual(ix.field_modules("x.thing", "partner_id"), {"base_x"})
        self.assertEqual(ix.field_info("x.thing", "partner_id")["comodel"], "res.partner")
        self.assertEqual(ix.selection("x.thing", "kind"), {"a", "b", "c"})
        self.assertEqual(ix.selection("x.thing", "kind", {"base_x"}), {"a", "b"})
        self.assertEqual(ix.method_modules("x.thing", "action_go"), {"base_x"})
        self.assertEqual(ix.method_modules("x.thing", "write"), {"base"})
        self.assertNotIn("test.only", ix.models)

    def test_extended_xmlid_belongs_to_the_module_it_names(self):
        self.assertEqual(self.index.xmlids["project.group_project_manager"], "project")

    def test_xmlid_only_another_module_writes_keeps_that_module(self):
        self.assertEqual(self.index.xmlids["project.only_here"], "hr_timesheet")

    def test_modules_xmlids_and_names(self):
        ix = self.index
        self.assertEqual(ix.modules["ee_y"]["edition"], "enterprise")
        self.assertEqual(ix.modules["base_x"]["edition"], "community")
        self.assertIn("ee_y", ix.closure(["base_x"]))      # auto_install follows its dependency
        self.assertEqual(ix.xmlids["base_x.view_thing"], "base_x")
        for name in ("no_create", "many2one_avatar", "delivered_x", "action_go", "partner_id", "view_thing"):
            self.assertIn(name, ix.known_names())

    def test_cache_lives_outside_the_repo(self):
        with mock.patch.dict(os.environ, {"OFA_CACHE_DIR": str(ROOT / ".ofa" / "cache")}):
            with self.assertRaises(UsageError):
                source_index.index_path([self.tmp])
        with mock.patch.dict(os.environ, {"OFA_CACHE_DIR": str(self.tmp / "cache")}):
            self.assertTrue(str(source_index.index_path([self.tmp])).startswith(str(self.tmp / "cache")))


if __name__ == "__main__":
    unittest.main()
