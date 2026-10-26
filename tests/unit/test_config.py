import os
import stat
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from ofa import config
from ofa.errors import EnvError, GuardError

SERVER = textwrap.dedent("""\
    [server]
    odoo_bin = "/opt/odoo/odoo-bin"
    python = "/opt/venv/bin/python"
    odoo_conf = "{conf}"
    url = "http://127.0.0.1:8070"
    odoo_version = "20.0"
    edition = "enterprise"
    template_db = "ofa_tpl_20"
    template_modules = ["crm", "sale_management"]
    log_file = "~/odoo20.log"
    xmlid_store = "ir_model_data"
    """)
HARDENED = "[options]\ndb_user = demo\ndata_dir = /srv/odoo-data\nlist_db = False\ndbfilter = ^ofa_demo_.*$\nmax_cron_threads = 0\n"


def make_target(name="t1", **kw):
    vals = dict(name=name, db=f"ofa_demo_{name}", url="http://127.0.0.1:8070", marker="m-1",
                api_key_file=f"/nonexistent/{name}.key", created_at="2026-10-26T00:00:00Z",
                odoo_version="20.0", edition="enterprise")
    vals.update(kw)
    return config.Target(**vals)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        patcher = mock.patch.dict(os.environ, {"OFA_CONFIG_DIR": str(self.tmp / "cfg")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conf = self.tmp / "odoo20.conf"
        self.conf.write_text(HARDENED)

    def write_config(self, extra=""):
        d = self.tmp / "cfg"
        d.mkdir(exist_ok=True)
        (d / "config.toml").write_text(SERVER.format(conf=self.conf) + extra)

    def test_missing_config(self):
        with self.assertRaises(EnvError) as cm:
            config.load()
        self.assertEqual(cm.exception.code, "CONFIG_MISSING")

    def test_missing_server_key(self):
        self.write_config()
        p = self.tmp / "cfg" / "config.toml"
        p.write_text(p.read_text().replace('xmlid_store = "ir_model_data"\n', ""))
        with self.assertRaises(EnvError) as cm:
            config.load()
        self.assertEqual(cm.exception.code, "CONFIG_INVALID")
        self.assertIn("xmlid_store", cm.exception.msg)

    def test_load_and_target_lookup(self):
        self.write_config()
        cfg = config.load()
        self.assertEqual(cfg.server.xmlid_store, "ir_model_data")
        self.assertEqual(cfg.server.template_modules, ("crm", "sale_management"))
        self.assertEqual(cfg.server.log_file, Path("~/odoo20.log").expanduser())
        with self.assertRaises(GuardError) as cm:
            cfg.target("nope")
        self.assertEqual(cm.exception.code, "NOT_REGISTERED")

    def test_server_reads_pg_and_data_dir_from_odoo_conf(self):
        # amendment 3 (critic F3)
        self.write_config()
        s = config.load().server
        self.assertEqual((s.db_user, s.db_host, s.db_port, s.data_dir), ("demo", "127.0.0.1", 5432, Path("/srv/odoo-data")))
        self.conf.write_text("[options]\ndb_user = demo\ndb_host = 10.1.1.1\ndb_port = 5433\n")
        self.assertEqual((s.db_host, s.db_port, s.data_dir), ("10.1.1.1", 5433, Path("~/.local/share/Odoo").expanduser()))
        self.conf.write_text("[options]\ndata_dir = /x\n")
        with self.assertRaises(EnvError):
            s.db_user

    def test_add_and_remove_target_roundtrip(self):
        self.write_config()
        config.add_target(make_target("t1"))
        config.add_target(make_target("t2", marker='quote " and \\ backslash'))
        cfg = config.load()
        self.assertEqual(sorted(cfg.targets), ["t1", "t2"])
        self.assertEqual(cfg.target("t2").marker, 'quote " and \\ backslash')
        self.assertEqual(cfg.server.template_modules, ("crm", "sale_management"))
        mode = stat.S_IMODE((self.tmp / "cfg" / "config.toml").stat().st_mode)
        self.assertEqual(mode, 0o600)
        config.remove_target("t1")
        self.assertEqual(sorted(config.load().targets), ["t2"])
        with self.assertRaises(GuardError):
            config.remove_target("t1")
        self.assertEqual([p.name for p in (self.tmp / "cfg").iterdir()], ["config.toml"])

    def test_dumps_is_valid_toml(self):
        raw = {"server": {"a": "x", "n": 3, "b": False, "l": ["p", "q"]}, "targets": {"t": {"db": "ofa_demo_t"}}}
        self.assertEqual(tomllib.loads(config.dumps(raw)), raw)

    def test_hardening_problems(self):
        self.assertEqual(config.hardening_problems(self.conf), [])
        self.conf.write_text("[options]\ndbfilter = .*\nlist_db = True\n")
        self.assertEqual(len(config.hardening_problems(self.conf)), 3)

    def test_api_key(self):
        key_file = self.tmp / "k.key"
        key_file.write_text("secret\n")
        self.assertEqual(make_target(api_key_file=str(key_file)).api_key(), "secret")
        with self.assertRaises(EnvError) as cm:
            make_target().api_key()
        self.assertEqual(cm.exception.code, "KEY_MISSING")
