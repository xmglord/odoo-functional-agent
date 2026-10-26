import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ofa import ROOT, cli, client, dump
from ofa.errors import ValidationError
from tests.fakeodoo import FakeOdoo
from tests.unit.test_client import KEY, MARKER, make_cfg

PLAN_DIR = ROOT / "tests" / "fixtures" / "dump" / "plan"
AUDIT = {"create_date": "2026-10-26 10:00:00", "write_date": "2026-10-26 10:00:00",
         "create_uid": [2, "Bot"], "write_uid": [2, "Bot"]}

EXPECTED = {
    "modules": ["crm", "sale_management"],
    "settings": {"op_020_settings": {"deposit_default_product_id": "product.product:Down payment",
                                     "group_discount_per_so_line": True}},
    "records": {
        "__ofa__.tag_vip": {"model": "res.partner.category", "values": {"color": 3, "name": "VIP", "parent_id": None}},
        "__ofa__.company_mx": {"model": "res.company", "values": {"country_id": "base.mx", "name": "Demo MX"}},
        "__ofa__.partner_vip": {"model": "res.partner", "values": {
            "category_id": ["__ofa__.tag_vip", "res.partner.category:Gold"], "name": "Demo customer"}},
    },
}

FIELDS = {
    "res.config.settings": {"group_discount_per_so_line": {"type": "boolean"},
                            "deposit_default_product_id": {"type": "many2one", "relation": "product.product"}},
    "res.partner.category": {"name": {"type": "char"}, "color": {"type": "integer"},
                             "parent_id": {"type": "many2one", "relation": "res.partner.category"}},
    "res.company": {"name": {"type": "char"}, "country_id": {"type": "many2one", "relation": "res.country"}},
    "res.partner": {"name": {"type": "char"}, "category_id": {"type": "many2many", "relation": "res.partner.category"}},
}


class World:
    """One fake demo DB. `o` shifts every id, so two worlds hold the same data under different ids."""

    def __init__(self, fake, o, reverse=False):
        self.fake, self.o = fake, o
        self.xmlids = [
            ("base", "main_company", "res.company", 1 + o),
            ("base", "mx", "res.country", 156 + o),
            ("__export__", f"res_country_{156 + o}_x{o}", "res.country", 156 + o),
            ("__ofa__", "tag_vip", "res.partner.category", 10 + o),
            ("__ofa__", "company_mx", "res.company", 20 + o),
            ("__ofa__", "partner_vip", "res.partner", 30 + o),
            ("__export__", f"product_product_{500 + o}_x{o}", "product.product", 500 + o),
        ]
        tags = [10 + o, 60 + o]
        self.rows = {
            "res.config.settings": {100 + o: {"group_discount_per_so_line": True, "deposit_default_product_id": [500 + o, "Down payment"]}},
            "res.partner.category": {10 + o: {"name": "VIP", "color": 3, "parent_id": False, "display_name": "VIP"},
                                     60 + o: {"name": "Gold", "color": 1, "parent_id": False, "display_name": "Gold"}},
            "res.company": {20 + o: {"name": "Demo MX", "country_id": [156 + o, "Mexico"]}},
            "res.partner": {30 + o: {"name": "Demo customer", "category_id": tags[::-1] if reverse else tags}},
            "product.product": {500 + o: {"display_name": "Down payment"}},
        }
        installed = ["sale_management", "crm"]
        fake.script("ir.config_parameter", "get_str", MARKER)
        fake.script("ir.module.module", "search_read",
                    [{"id": n + o, "name": m} for n, m in enumerate(installed[::-1] if reverse else installed)])
        fake.script("ir.model.data", "search_read", self.imd)
        fake.script("res.config.settings", "create", [100 + o])
        for model in self.rows:
            fake.script(model, "read", self.read(model))
        for model, desc in FIELDS.items():
            fake.script(model, "fields_get", lambda req, desc=desc: {k: desc[k] for k in req.params["allfields"]})

    def imd(self, req):
        d = dict((c[0], c[2]) for c in req.params["domain"])
        if "module" in d:
            hits = [x for x in self.xmlids if x[0] == d["module"] and x[1] == d["name"]]
            return [{"id": 1, "model": m, "res_id": r} for _, _, m, r in hits]
        hits = [x for x in self.xmlids if x[2] == d["model"] and x[3] in d["res_id"]]
        return [{"id": 1, "module": mod, "name": n, "res_id": r} for mod, n, _, r in hits]

    def read(self, model):
        def handler(req):
            # Like a server that also sends audit columns: dump must drop them.
            return [{"id": i, **AUDIT, **{f: self.rows[model][i].get(f, False) for f in req.params["fields"]}}
                    for i in req.ids]
        return handler


class DumpTest(unittest.TestCase):
    def world(self, o, reverse=False):
        fake = FakeOdoo(key=KEY, db="ofa_demo_t1").__enter__()
        self.addCleanup(fake.__exit__, None, None, None)
        World(fake, o, reverse)
        cfg = make_cfg(fake.url)
        self.addCleanup(shutil.rmtree, Path(cfg.target("t1").api_key_file).parent)
        return fake, cfg

    def dump_text(self, o, reverse=False):
        fake, cfg = self.world(o, reverse)
        c = client.open_client("t1", cfg=cfg)
        return dump.canonical(dump.dump(c, dump.load_plan(PLAN_DIR))), fake

    def test_normalization(self):
        text, fake = self.dump_text(0)
        self.assertEqual(json.loads(text), EXPECTED)
        for audit in ("create_date", "write_date", "create_uid", "write_uid", '"id"'):
            self.assertNotIn(audit, text)
        # settings were read in the op's company context
        ctx = fake.calls("res.config.settings", "create")[0].context
        self.assertEqual(ctx, {"allowed_company_ids": [1]})
        # call_method ops are not dumped, and only plan fields were read
        self.assertEqual(sorted(fake.calls("res.company", "read")[0].params["fields"]), ["country_id", "name"])

    def test_byte_identical_across_dbs_with_different_ids(self):
        a, _ = self.dump_text(0)
        b, _ = self.dump_text(1000, reverse=True)
        self.assertEqual(a.encode(), b.encode())
        self.assertTrue(a.endswith("}\n"))
        self.assertIn('\n  "modules": [\n    "crm",', a)  # sorted keys, 2-space indent

    def test_missing_record_is_visible(self):
        fake, cfg = self.world(0)
        w = World(fake, 0)
        w.xmlids = [x for x in w.xmlids if x[1] != "company_mx"]
        c = client.open_client("t1", cfg=cfg)
        out = dump.dump(c, dump.load_plan(PLAN_DIR))
        self.assertEqual(out["records"]["__ofa__.company_mx"], {"model": "res.company", "values": None})

    def test_bad_plan(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        for content in ("{nope", json.dumps({"format": "ofa.plan/0", "operations": []}),
                        json.dumps({"format": "ofa.plan/1", "operations": [{"id": "op_1", "type": "upsert_record"}]})):
            (tmp / "plan.json").write_text(content)
            with self.assertRaises(ValidationError):
                dump.load_plan(tmp)
        (tmp / "plan.json").unlink()
        with self.assertRaises(ValidationError):
            dump.load_plan(tmp)

    def test_cli_out_file_and_stdout(self):
        fake, cfg = self.world(0)
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        out_file = tmp / "dump.json"
        out = io.StringIO()
        with mock.patch("ofa.config.load", return_value=cfg), contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["dump", str(PLAN_DIR), "--target", "t1", "--out", str(out_file)]), 0)
            self.assertEqual(cli.main(["dump", str(PLAN_DIR), "--target", "t1"]), 0)
        self.assertEqual(json.loads(out_file.read_text()), EXPECTED)
        self.assertEqual(out.getvalue(), out_file.read_text())


if __name__ == "__main__":
    unittest.main()
