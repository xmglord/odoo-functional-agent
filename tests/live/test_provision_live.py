"""Live provisioning test against the local stack. Runs only with OFA_LIVE=1."""
import os
import subprocess
import unittest

from ofa import ROOT, client, config, pg

LIVE = os.environ.get("OFA_LIVE") == "1"
NAME = "t08_live"


def ofa(*args):
    return subprocess.run([str(ROOT / "bin" / "ofa"), *args], capture_output=True, text=True, timeout=600)


@unittest.skipUnless(LIVE, "set OFA_LIVE=1 to run live tests")
class ProvisionLiveTest(unittest.TestCase):
    def setUp(self):
        self.assertEqual(ofa("server", "start").returncode, 0)

    def tearDown(self):
        if NAME in config.load().targets:
            ofa("drop", NAME)

    def test_provision_reset_drop(self):
        self.assertEqual(ofa("provision", NAME).returncode, 0)
        c = client.open_client(NAME)
        self.assertEqual(c.call("res.users", "search", domain=[["login", "=", "ofa_bot"]]), [c.bot_uid()])
        first_marker = config.load().target(NAME).marker
        # Same name again: the shared server must not serve the dropped DB's cached state.
        self.assertEqual(ofa("reset", NAME).returncode, 0)
        self.assertNotEqual(config.load().target(NAME).marker, first_marker)
        client.open_client(NAME).call("res.users", "context_get")
        r = ofa("drop", NAME)
        self.assertEqual(r.returncode, 0, r.stderr)
        server = config.load().server
        self.assertFalse(pg.db_exists(server, f"ofa_demo_{NAME}"))
        self.assertFalse((server.data_dir / "filestore" / f"ofa_demo_{NAME}").exists())
        self.assertNotIn(NAME, config.load().targets)
