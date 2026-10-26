import unittest

from ofa import refs
from ofa.errors import UsageError, ValidationError
from tests.unit.test_client import FakeCase


class RefsTest(FakeCase):
    def setUp(self):
        super().setUp()
        self.c = self.open()

    def test_ref_var_search_set_add_create(self):
        self.fake.script("ir.model.data", "search_read", lambda req: [{"id": 1, "model": "res.country", "res_id": 156}]
                         if req.params["domain"] == [["module", "=", "base"], ["name", "=", "mx"]] else [])
        self.fake.script("res.partner.category", "search", [9])
        value = {
            "country_id": {"$ref": "base.mx"},
            "user_id": {"$var": "uid"},
            "nested": [{"$search": {"model": "res.partner.category", "domain": [["name", "=", "VIP"]]}}],
            "category_id": {"$set": [{"$var": "uid"}, 3]},
            "tag_ids": {"$add": [{"$ref": "base.mx"}]},
            "line_ids": {"$create": [{"name": "x", "partner_id": {"$var": "uid"}}]},
            "plain": {"a": 1, "$ref": "not a ref because two keys"},
        }
        out = refs.resolve(self.c, value, {"uid": 2})
        self.assertEqual(out, {
            "country_id": 156, "user_id": 2, "nested": [9],
            "category_id": [[6, 0, [2, 3]]], "tag_ids": [[4, 156]],
            "line_ids": [[0, 0, {"name": "x", "partner_id": 2}]],
            "plain": {"a": 1, "$ref": "not a ref because two keys"},
        })

    def test_errors(self):
        self.fake.script("ir.model.data", "search_read", [])
        self.fake.script("res.partner", "search", [1, 2])
        cases = [({"$ref": "base.nope"}, "UNRESOLVED_REF"), ({"$ref": "nodot"}, "BAD_REF"),
                 ({"$var": "x"}, "UNRESOLVED_VAR"),
                 ({"$search": {"model": "res.partner", "domain": []}}, "SEARCH_NOT_UNIQUE"),
                 ({"$set": ["a"]}, "BAD_REF")]
        for value, code in cases:
            with self.assertRaises(ValidationError, msg=code) as cm:
                refs.resolve(self.c, value, {})
            self.assertEqual(cm.exception.code, code)

    def test_ofa_store_roundtrip(self):
        rows = []

        def search_read(req):
            name = req.params["domain"][1][2]
            return [r for r in rows if r["name"] == name]

        def create(req):
            for vals in req.params["vals_list"]:
                rows.append({"id": len(rows) + 1, **vals})
            return [rows[-1]["id"]]

        def write(req):
            for r in rows:
                if r["id"] in req.ids:
                    r.update(req.params["vals"])
            return True

        self.fake.script("ir.model.data", "search_read", search_read)
        self.fake.script("ir.model.data", "create", create)
        self.fake.script("ir.model.data", "write", write)
        self.assertIsNone(refs.lookup_ofa(self.c, "tax_16"))
        refs.store_ofa(self.c, "tax_16", "account.tax", 5)
        self.assertEqual(refs.lookup_ofa(self.c, "tax_16"), ("account.tax", 5))
        refs.store_ofa(self.c, "tax_16", "account.tax", 5)
        self.assertEqual(len(self.fake.calls("ir.model.data", "create")), 1)
        self.assertEqual(self.fake.calls("ir.model.data", "write"), [])
        refs.store_ofa(self.c, "tax_16", "account.tax", 6)
        self.assertEqual(refs.lookup_ofa(self.c, "tax_16"), ("account.tax", 6))
        self.assertEqual(rows[0]["module"], "__ofa__")
        self.assertEqual(refs.resolve(self.c, {"$ref": "__ofa__.tax_16"}, {}), 6)

    def test_unimplemented_backend(self):
        self.c.xmlid_store = "config_parameter"
        with self.assertRaises(UsageError):
            refs.lookup_ofa(self.c, "x")


class NormalizeReadTest(unittest.TestCase):
    def test_shapes(self):
        # Live shapes from spike S8: many2one [id, name], x2many id list.
        self.assertEqual(refs.normalize_read([233, "United States"]), 233)
        self.assertEqual(refs.normalize_read(233), 233)
        self.assertEqual(refs.normalize_read([7, 3]), [3, 7])
        self.assertEqual(refs.normalize_read([]), [])
        self.assertIs(refs.normalize_read(False), False)
        self.assertEqual(refs.normalize_read("text"), "text")
