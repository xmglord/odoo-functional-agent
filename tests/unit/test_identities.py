"""Test identities: scenario steps `as` a test user, roles from plan ops, the administrator-group guard."""
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from ofa import executor, identities, scenario
from ofa.errors import GuardError, ValidationError
from tests.unit.test_client import KEY, FakeCase

BUYER_KEY = "buyer-key"
BOT, BUYER, BOSS = 8, 51, 52
GROUPS = {"base.group_user": 1, "base.group_system": 2, "base.group_erp_manager": 3,
          "purchase.group_purchase_user": 30, "fixture.group_implies_settings": 40}
IMPLIED = {1: [], 2: [1], 3: [1], 30: [1], 40: [1, 3]}
USERS = {BOT: "ofa_bot", BUYER: "ofa_user_1", BOSS: "ofa_user_2"}


class IdentityCase(FakeCase):
    def setUp(self):
        super().setUp()
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        patcher = mock.patch.dict(os.environ, {"OFA_CONFIG_DIR": str(tmp)})
        patcher.start()
        self.addCleanup(patcher.stop)
        identities.write_key("ofa_demo_t1", "ofa_user_1", BUYER_KEY)
        self.fake.extra_keys.add(BUYER_KEY)
        self.groups = {BOT: [1, 2], BUYER: [1, 30], BOSS: [1]}
        self.roles = {BUYER: "hf_buyer"}
        self.writes = []
        f = self.fake
        f.script("ir.model.data", "search_read", self._imd)
        f.script("res.users", "search",
                 lambda req: [u for u, login in USERS.items()
                              if ["login", "=", login] in req.params["domain"] or ["id", "=", u] in req.params["domain"]])
        f.script("res.users", "read", self._read_users)
        f.script("res.users", "write", self._write_users)
        f.script("res.groups", "read", lambda req: [{"id": g, "all_implied_ids": IMPLIED[g]} for g in req.ids])
        f.script("ir.module.module", "search_read", [])

    def _imd(self, req):
        d = dict((c[0], c[2]) for c in req.params["domain"])
        if d.get("model") == "res.users" and "res_id" in d:
            key = self.roles.get(d["res_id"])
            return [{"name": key}] if key else []
        if d.get("model") == "res.groups":
            names = {v: k for k, v in GROUPS.items()}
            return [{"module": names[g].partition(".")[0], "name": names[g].partition(".")[2], "res_id": g}
                    for g in d["res_id"]]
        if d.get("module") == "__ofa__":
            uid = next((u for u, k in self.roles.items() if k == d.get("name")), None)
            return [{"id": 1, "model": "res.users", "res_id": uid}] if uid else []
        xmlid = f"{d.get('module')}.{d.get('name')}"
        return [{"id": 1, "model": "res.groups", "res_id": GROUPS[xmlid]}] if xmlid in GROUPS else []

    def _all(self, uid):
        out = set(self.groups[uid])
        for g in self.groups[uid]:
            out |= set(IMPLIED[g])
        return sorted(out)

    def _read_users(self, req):
        rows = []
        for uid in req.ids:
            row = {"id": uid, "login": USERS[uid], "all_group_ids": self._all(uid), "group_ids": self.groups[uid]}
            rows.append({k: v for k, v in row.items() if k == "id" or k in req.params["fields"]})
        return rows

    def _write_users(self, req):
        self.writes.append((req.ids, req.params["vals"]))
        if "group_ids" in req.params["vals"]:
            for uid in req.ids:
                self.groups[uid] = list(req.params["vals"]["group_ids"][0][2])
        return True

    def scenario(self, steps, **top):
        data = {"format": "ofa.scenario/1", "id": "approval_as_buyer", "area": "purchase_inventory",
                "odoo_version": "20.0", "edition": "community", "description": "x", "steps": steps, **top}
        return scenario.validate(data)


class ValidateTest(IdentityCase):
    def test_as_names_a_declared_user_or_a_reference(self):
        step = {"id": "s010", "action": "search", "model": "purchase.order", "domain": []}
        self.scenario([{**step, "as": {"$ref": "__ofa__.hf_buyer"}}])
        with self.assertRaises(ValidationError) as cm:
            self.scenario([{**step, "as": "buyer"}])
        self.assertIn("not declared in users", cm.exception.msg)
        with self.assertRaises(ValidationError) as cm:
            self.scenario([step], users={"buyer": {"login": "ofa_bot", "groups": [{"$ref": "base.group_user"}]}})
        self.assertIn("must be a test user", cm.exception.msg)
        with self.assertRaises(ValidationError):
            self.scenario([{**step, "id": "identities"}])


class RunAsTest(IdentityCase):
    def test_steps_as_the_plan_role_use_its_key_and_the_bot_approves(self):
        # T24 need 1: a buyer's order of 50,000 or more waits for approval; the manager (the bot) approves it.
        f = self.fake
        f.script("purchase.order", "create", [5])
        f.script("purchase.order", "button_confirm", True)
        f.script("purchase.order", "button_approve", True)
        f.script("purchase.order", "read", lambda req: [{"id": 5, "state": "to approve"}])
        buyer = {"$ref": "__ofa__.hf_buyer"}
        sc = self.scenario([
            {"id": "s010", "action": "create", "model": "purchase.order", "values": {"partner_id": 1}, "save_as": "po",
             "as": buyer},
            {"id": "s020", "action": "call", "model": "purchase.order", "target": {"$var": "po"},
             "method": "button_confirm", "as": buyer},
            {"id": "s030", "action": "assert", "model": "purchase.order", "target": {"$var": "po"},
             "expect": {"fields": {"state": {"eq": "to approve"}}}, "as": buyer},
            {"id": "s040", "action": "call", "model": "purchase.order", "target": {"$var": "po"},
             "method": "button_approve"},
        ])
        result, _, _ = scenario.run(self.open(), sc)
        self.assertEqual(result["status"], "pass", result)
        auth = {(r.method): r.headers["authorization"] for r in f.calls("purchase.order")}
        self.assertEqual(auth, {"create": f"bearer {BUYER_KEY}", "button_confirm": f"bearer {BUYER_KEY}",
                                "read": f"bearer {BUYER_KEY}", "button_approve": f"bearer {KEY}"})
        self.assertEqual(result["identities"], [{"login": "ofa_user_1", "source": "plan role __ofa__.hf_buyer",
                                                 "groups": ["base.group_user", "purchase.group_purchase_user"]}])
        self.assertEqual(self.writes, [])  # a plan role is never rewritten by a scenario

    def test_declared_user_with_an_implied_admin_group_is_refused_before_any_write(self):
        self.fake.script("purchase.order", "search", [])
        sc = self.scenario([{"id": "s010", "action": "search", "model": "purchase.order", "domain": [], "as": "boss"}],
                           users={"boss": {"login": "ofa_user_2",
                                           "groups": [{"$ref": "fixture.group_implies_settings"}]}})
        result, _, _ = scenario.run(self.open(), sc)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["steps"][0]["id"], "identities")
        self.assertIn("ADMIN_GROUP_ON_TEST_USER", result["steps"][0]["message"])
        self.assertEqual(self.writes, [])
        self.assertEqual(self.fake.calls("purchase.order"), [])

    def test_declaring_a_plan_role_user_is_refused(self):
        sc = self.scenario([{"id": "s010", "action": "search", "model": "purchase.order", "domain": [], "as": "b"}],
                           users={"b": {"login": "ofa_user_1", "groups": [{"$ref": "base.group_user"}]}})
        result, _, _ = scenario.run(self.open(), sc)
        self.assertIn("TEST_USER_HAS_ROLE", result["steps"][0]["message"])
        self.assertEqual(self.writes, [])

    def test_declared_user_gets_exactly_its_groups_and_is_marked_an_assumption(self):
        self.roles = {}
        self.fake.script("purchase.order", "search", [])
        sc = self.scenario([{"id": "s010", "action": "search", "model": "purchase.order", "domain": [], "as": "b"}],
                           users={"b": {"login": "ofa_user_1", "groups": [{"$ref": "purchase.group_purchase_user"}]}})
        result, _, _ = scenario.run(self.open(), sc)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(self.writes, [([BUYER], {"group_ids": [[6, 0, [30]]]})])
        self.assertEqual(result["identities"][0]["source"], "scenario users (assumption)")


class ApplyGuardTest(IdentityCase):
    def op(self, groups):
        return {"id": "op_010_role", "type": "upsert_record", "model": "res.users", "key": "hf_boss",
                "match": [["login", "=", "ofa_user_2"]], "values": {"group_ids": groups}}

    def test_role_op_refuses_an_admin_group_before_writing(self):
        self.roles = {}
        self.fake.script("ir.model.data", "create", [9])
        op = self.op({"$set": [{"$ref": "base.group_system"}]})
        with self.assertRaises(GuardError) as cm:
            executor._upsert_record(self.open(), op, None)
        self.assertEqual(cm.exception.code, "ADMIN_GROUP_ON_TEST_USER")
        self.assertEqual(self.writes, [])
        # Seen live: the key was stored first, so the refused user later showed as a plan role.
        self.assertEqual(self.fake.calls("ir.model.data", "create"), [])

    def test_role_op_must_set_not_add(self):
        self.roles = {}
        self.fake.script("ir.model.data", "create", [9])
        op = self.op({"$add": [{"$ref": "purchase.group_purchase_user"}]})
        with self.assertRaises(ValidationError) as cm:
            executor._upsert_record(self.open(), op, None)
        self.assertEqual(cm.exception.code, "TEST_USER_NEEDS_SET")
        self.assertEqual(self.writes, [])

    def test_role_op_writes_exactly_the_plan_groups(self):
        self.roles = {}
        self.fake.script("ir.model.data", "create", [9])
        self.groups[BOSS] = [1, 40]  # what the user had before: replaced, not kept
        op = self.op({"$set": [{"$ref": "purchase.group_purchase_user"}]})
        status, ids = executor._upsert_record(self.open(), op, None)
        self.assertEqual((status, ids), ("adopted", [BOSS]))
        self.assertEqual(self.writes[0], ([BOSS], {"group_ids": [[6, 0, [30]]]}))
        self.assertEqual(self.groups[BOSS], [30])

    def test_role_op_cannot_change_the_language(self):
        # expect_error texts are English; Odoo translates refusals to the acting user's language.
        self.roles = {}
        op = {**self.op({"$set": [{"$ref": "purchase.group_purchase_user"}]})}
        op["values"] = {**op["values"], "lang": "es_MX"}
        with self.assertRaises(GuardError) as cm:
            executor._upsert_record(self.open(), op, None)
        self.assertEqual(cm.exception.code, "FIXED_LANG")
        self.assertEqual(self.writes, [])
