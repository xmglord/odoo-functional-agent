import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ofa import config, identities, pg, provision, server
from ofa.errors import EnvError, GuardError, UsageError
from tests.unit.test_config import HARDENED, SERVER, make_target


USER_KEYS = {"ofa_user_1": "u1key", "ofa_user_2": "u2key", "ofa_user_3": "u3key"}
USER_KEY_LINES = "".join(f"OFA_USER_KEY={login}={key}\n" for login, key in USER_KEYS.items())


class ProvisionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        patcher = mock.patch.dict(os.environ, {"OFA_CONFIG_DIR": str(self.tmp / "cfg")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conf = self.tmp / "odoo20.conf"
        self.conf.write_text(HARDENED.replace("/srv/odoo-data", str(self.tmp / "data")))
        (self.tmp / "cfg").mkdir()
        (self.tmp / "cfg" / "config.toml").write_text(SERVER.format(conf=self.conf))
        self.pg = {name: mock.patch.object(pg, name).start() for name in
                   ("db_exists", "create_from_template", "drop_db", "read_marker", "psql")}
        self.addCleanup(mock.patch.stopall)

    def quiet(self, fn, *args):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = fn(*args, log=lambda *_: None)
        return code, err.getvalue()


class NameTest(unittest.TestCase):
    def test_db_name(self):
        self.assertEqual(provision.db_name("t08a"), "ofa_demo_t08a")
        for bad in ("", "T08", "a-b", "a b", "x" * 41, "a;drop"):
            with self.assertRaises(UsageError, msg=bad):
                provision.db_name(bad)

    def test_pg_ident(self):
        self.assertEqual(pg._ident("ofa_demo_x"), '"ofa_demo_x"')
        for bad in ('x"; drop', "X", "a-b"):
            with self.assertRaises(UsageError):
                pg._ident(bad)


class DropTest(ProvisionCase):
    def register(self, name, **kw):
        config.add_target(make_target(name, marker="m-ok", **kw))

    def test_not_registered(self):
        code, err = self.quiet(provision.drop, ["xm"])
        self.assertEqual(code, 3)
        self.assertIn("NOT_REGISTERED", err)
        self.pg["drop_db"].assert_not_called()

    def test_bad_name_registered_by_hand(self):
        self.register("xm", db="xm")
        code, err = self.quiet(provision.drop, ["xm"])
        self.assertEqual(code, 3)
        self.assertIn("BAD_NAME", err)
        self.pg["drop_db"].assert_not_called()

    def test_marker_missing_and_mismatch(self):
        self.register("t1")
        self.pg["db_exists"].return_value = True
        for marker, code_name in ((None, "MARKER_MISSING"), ("other", "MARKER_MISMATCH")):
            self.pg["read_marker"].return_value = marker
            code, err = self.quiet(provision.drop, ["t1"])
            self.assertEqual(code, 3)
            self.assertIn(code_name, err)
        self.pg["drop_db"].assert_not_called()
        self.assertIn("t1", config.load().targets)

    def test_match_drops_and_cleans(self):
        self.register("t1")
        key = config.config_dir() / "keys" / "ofa_demo_t1.key"
        key.parent.mkdir()
        key.write_text("k")
        self.pg["db_exists"].return_value = True
        self.pg["read_marker"].return_value = "m-ok"
        code, _ = self.quiet(provision.drop, ["t1"])
        self.assertEqual(code, 0)
        self.pg["drop_db"].assert_called_once()
        self.assertEqual(self.pg["drop_db"].call_args.args[1], "ofa_demo_t1")
        self.assertFalse(key.exists())
        self.assertNotIn("t1", config.load().targets)

    def test_multi_name_continues_and_returns_highest(self):
        self.register("t1")
        self.pg["db_exists"].return_value = True
        self.pg["read_marker"].return_value = "m-ok"
        code, err = self.quiet(provision.drop, ["nope", "t1"])
        self.assertEqual(code, 3)
        self.pg["drop_db"].assert_called_once()


class ProvisionTest(ProvisionCase):
    def test_refuses_existing_db_and_target(self):
        self.pg["db_exists"].return_value = True
        with self.assertRaises(UsageError):
            provision.provision("t1", log=lambda *_: None)
        self.pg["create_from_template"].assert_not_called()
        config.add_target(make_target("t2"))
        with self.assertRaises(UsageError):
            provision.provision("t2", log=lambda *_: None)

    def test_keys_are_private_and_drop_removes_them(self):
        # The test users' keys get the bot key's protection: 0600 files in a 0700 dir, gone with the target.
        self.pg["db_exists"].return_value = False
        with mock.patch.object(provision, "run_provision_shell", return_value=("botkey", USER_KEYS)), \
                mock.patch.object(provision.client, "open_client"):
            provision.provision("t1", log=lambda *_: None)
        keys = config.config_dir() / "keys"
        files = [keys / "ofa_demo_t1.key"] + [identities.key_path("ofa_demo_t1", l) for l in identities.LOGINS]
        self.assertEqual(oct(keys.stat().st_mode & 0o777), "0o700")
        for f in files:
            with self.subTest(f=f.name):
                self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
        self.assertEqual(identities.key_path("ofa_demo_t1", "ofa_user_2").read_text().strip(), "u2key")
        self.pg["db_exists"].return_value = True
        self.pg["read_marker"].return_value = config.load().target("t1").marker
        code, _ = self.quiet(provision.drop, ["t1"])
        self.assertEqual(code, 0)
        self.assertEqual([f for f in files if f.exists()], [])

    def test_rollback_on_shell_failure(self):
        self.pg["db_exists"].return_value = False
        with mock.patch.object(provision, "run_provision_shell", side_effect=EnvError("SHELL_FAILED", "x")):
            with self.assertRaises(EnvError):
                provision.provision("t1", log=lambda *_: None)
        self.pg["drop_db"].assert_called_once()
        self.assertEqual(config.load().targets, {})
        self.assertFalse((config.config_dir() / "keys" / "ofa_demo_t1.key").exists())

    def test_shell_sentinel_and_no_key_leak(self):
        s = config.load().server
        ok = subprocess.CompletedProcess([], 0, stdout="noise\nOFA_KEY=abc123\n" + USER_KEY_LINES, stderr="")
        with mock.patch.object(subprocess, "run", return_value=ok) as run:
            self.assertEqual(provision.run_provision_shell(s, "ofa_demo_t1", "m-1"), ("abc123", USER_KEYS))
        argv, script = run.call_args.args[0], run.call_args.kwargs["input"]
        self.assertEqual(argv[2], "shell")
        self.assertIn("ICP.set_str('ofa.demo_marker', 'm-1')", script)
        self.assertIn("orm_signaling_registry", script)
        self.assertIn("for login in ['ofa_user_1', 'ofa_user_2', 'ofa_user_3']:", script)
        self.assertEqual(script.count("'lang': 'en_US',"), 2)  # the bot and every test user
        # A missing test-user key is a failed provision, not a target that cannot run `as` steps later.
        partial = subprocess.CompletedProcess([], 0, stdout="OFA_KEY=abc123\nOFA_USER_KEY=ofa_user_1=u1\n", stderr="")
        with mock.patch.object(subprocess, "run", return_value=partial):
            with self.assertRaises(EnvError) as cm:
                provision.run_provision_shell(s, "ofa_demo_t1", "m-1")
        self.assertNotIn("u1", str(cm.exception))
        bad = subprocess.CompletedProcess([], 1, stdout="OFA_KEY=secretpart\nTraceback", stderr="boom")
        with mock.patch.object(subprocess, "run", return_value=bad):
            with self.assertRaises(EnvError) as cm:
                provision.run_provision_shell(s, "ofa_demo_t1", "m-1")
        self.assertNotIn("secretpart", str(cm.exception))


class TemplateTest(ProvisionCase):
    def test_refuses_other_names(self):
        for name in ("ofa_demo_x", "xm", "ofa_tpl_19"):
            with self.assertRaises(GuardError):
                provision.template_build(name, log=lambda *_: None)
        self.pg["drop_db"].assert_not_called()


class ServerTest(ProvisionCase):
    def test_start_refuses_unhardened_before_anything(self):
        self.conf.write_text("[options]\ndb_user = demo\nlist_db = False\ndbfilter = ^ofa_demo_.*$\n")
        with mock.patch.object(subprocess, "Popen") as popen:
            with self.assertRaises(GuardError) as cm:
                server.start(config.load().server, log=lambda *_: None)
        self.assertEqual((cm.exception.code, cm.exception.exit_code), ("SERVER_UNHARDENED", 3))
        popen.assert_not_called()

    def test_stop_when_not_running(self):
        out = []
        self.assertEqual(server.stop(config.load().server, log=out.append), 0)
        self.assertEqual(out, ["not running"])
