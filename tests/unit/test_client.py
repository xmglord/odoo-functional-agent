import atexit
import json
import shutil
import socket
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from ofa import client, config
from ofa.errors import EnvError, GuardError, OdooError, UsageError
from tests.fakeodoo import FakeOdoo, Response, error_body
from tests.unit.test_config import make_target

KEY = "sekret-api-key-123"
MARKER = "6f1c2d1e-0000-4000-8000-000000000001"
TRACE = "Traceback (most recent call last):\n  File \"/home/someone/odoo/x.py\", line 1"


_TMP_DIRS = []
atexit.register(lambda: [shutil.rmtree(d, ignore_errors=True) for d in _TMP_DIRS])


def make_cfg(url, key=KEY, db="ofa_demo_t1", store="ir_model_data"):
    tmp = Path(tempfile.mkdtemp())
    _TMP_DIRS.append(tmp)
    key_file = tmp / "k.key"
    key_file.write_text(key)
    server = config.ServerCfg(odoo_bin=Path("/x/odoo-bin"), python=Path("/x/python"), odoo_conf=Path("/x/odoo20.conf"),
                              url=url, odoo_version="20.0", edition="enterprise", template_db="ofa_tpl_20",
                              template_modules=("crm",), log_file=Path("/x/log"), xmlid_store=store)
    target = make_target("t1", db=db, url=url, marker=MARKER, api_key_file=str(key_file))
    return config.Config(server=server, targets={"t1": target})


class FakeCase(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOdoo(key=KEY, db="ofa_demo_t1").__enter__()
        self.addCleanup(self.fake.__exit__, None, None, None)
        self.fake.script("ir.config_parameter", "get_str", MARKER)
        self.cfg = make_cfg(self.fake.url)

    def open(self):
        return client.open_client("t1", cfg=self.cfg)


class OpenClientTest(FakeCase):
    def test_marker_ok_and_headers(self):
        c = self.open()
        req = self.fake.calls("ir.config_parameter", "get_str")[0]
        self.assertEqual(req.params, {"key": "ofa.demo_marker"})
        self.assertEqual(req.headers["authorization"], f"bearer {KEY}")
        self.assertEqual(req.headers["x-odoo-database"], "ofa_demo_t1")
        self.assertEqual(c.xmlid_store, "ir_model_data")

    def test_marker_missing_empty_string_and_null(self):
        # amendment 10 (grounder F4): get_str returns "" for a missing key
        for value in ("", None):
            self.fake.script("ir.config_parameter", "get_str", value)
            with self.assertRaises(GuardError) as cm:
                self.open()
            self.assertEqual(cm.exception.code, "MARKER_MISSING")

    def test_marker_mismatch(self):
        self.fake.script("ir.config_parameter", "get_str", "other")
        with self.assertRaises(GuardError) as cm:
            self.open()
        self.assertEqual(cm.exception.code, "MARKER_MISMATCH")

    def test_static_guard_runs_before_any_call(self):
        cfg = make_cfg("http://10.0.0.5:8070")
        with self.assertRaises(GuardError) as cm:
            client.open_client("t1", cfg=cfg)
        self.assertEqual(cm.exception.code, "NOT_LOOPBACK")
        with self.assertRaises(GuardError) as cm:
            client.open_client("other", cfg=cfg)
        self.assertEqual(cm.exception.code, "NOT_REGISTERED")
        self.assertEqual(self.fake.requests, [])

    def test_constructor_is_private(self):
        with self.assertRaises(UsageError):
            client.OdooClient(self.cfg.target("t1"), KEY, "ir_model_data")


class CallTest(FakeCase):
    def test_body_and_call_log(self):
        c = self.open()
        self.fake.script("res.partner", "write", True)
        self.assertTrue(c.call("res.partner", "write", ids=[7], vals={"comment": "x"}, context={"lang": "en_US"}))
        req = self.fake.calls("res.partner", "write")[0]
        self.assertEqual(req.body, {"vals": {"comment": "x"}, "ids": [7], "context": {"lang": "en_US"}})
        entry = c.call_log[-1]
        self.assertEqual(set(entry), {"ts", "model", "method", "ids", "duration_ms", "status"})
        self.assertEqual((entry["model"], entry["method"], entry["ids"], entry["status"]), ("res.partner", "write", [7], 200))

    def test_record_methods_need_ids(self):
        # amendment 9 (grounder F3)
        c = self.open()
        for method in ("write", "read", "action_confirm", "button_validate", "execute", "process"):
            for ids in (None, []):
                with self.assertRaises(UsageError, msg=method):
                    c.call("sale.order", method, ids=ids)
        with self.assertRaises(UsageError):
            c.call("res.partner", "search", ids=[1], domain=[])
        self.fake.script("res.partner", "name_search_custom", [])
        c.call("res.partner", "name_search_custom", api_model=True)

    def test_html_404_is_db_not_served(self):
        c = self.open()
        self.fake.script("res.partner", "search", Response(404, "<!doctype html><h1>Not Found</h1>", "text/html"))
        with self.assertRaises(EnvError) as cm:
            c.call("res.partner", "search", domain=[])
        self.assertEqual((cm.exception.code, cm.exception.exit_code), ("DB_NOT_SERVED", 4))

    def test_json_404_is_odoo_error(self):
        c = self.open()
        self.fake.script("res.partner", "search", Response(404, error_body("werkzeug.exceptions.NotFound", "nope")))
        with self.assertRaises(OdooError) as cm:
            c.call("res.partner", "search", domain=[])
        self.assertEqual((cm.exception.status, cm.exception.name), (404, "werkzeug.exceptions.NotFound"))

    def test_fake_rejects_wrong_param_names(self):
        c = self.open()
        with self.assertRaises(OdooError) as cm:
            c.call("res.partner", "create", values=[{}])
        self.assertEqual((cm.exception.status, cm.exception.name), (422, "werkzeug.exceptions.UnprocessableEntity"))

    def test_fake_rejects_ids_on_api_model_primitive(self):
        # Raw request: the client itself refuses ids on search_read before sending.
        req = urllib.request.Request(f"{self.fake.url}/json/2/res.partner/search_read", method="POST",
                                     data=json.dumps({"ids": [1], "domain": []}).encode(),
                                     headers={"Authorization": f"bearer {KEY}", "X-Odoo-Database": "ofa_demo_t1"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        with cm.exception as e:
            self.assertEqual((e.code, json.loads(e.read())["name"]), (422, "werkzeug.exceptions.UnprocessableEntity"))

    def test_connection_refused_is_server_down(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        cfg = make_cfg(f"http://127.0.0.1:{port}")
        with self.assertRaises(EnvError) as cm:
            client.open_client("t1", cfg=cfg)
        self.assertEqual(cm.exception.code, "SERVER_DOWN")

    def test_debug_and_key_never_leak(self):
        c = self.open()
        self.fake.script("res.partner", "write",
                         Response(500, error_body("odoo.exceptions.AccessError", "no access", debug=TRACE)))
        with self.assertRaises(OdooError) as cm:
            c.call("res.partner", "write", ids=[1], vals={})
        e = cm.exception
        texts = [str(e), repr(e), e.msg, e.message, e.name, repr(vars(e)), repr(c.call_log), repr(c)]
        texts.append(f"ofa: {e.label}: {e.msg}")  # what cli.main prints
        for t in texts:
            self.assertNotIn("Traceback", t)
            self.assertNotIn("/home/someone", t)
            self.assertNotIn(KEY, t)
        self.assertIsNone(e.__cause__)
        self.assertTrue(e.__suppress_context__)

    def test_bot_uid(self):
        c = self.open()
        self.fake.script("res.users", "search", [42])
        self.assertEqual(c.bot_uid(), 42)
        self.assertEqual(self.fake.calls("res.users", "search")[0].params["domain"], [["login", "=", "ofa_bot"]])
