import contextlib
import io
import sys
import types
import unittest
from unittest import mock

from ofa import cli, guard
from ofa.errors import GuardError
from tests.unit.test_config import make_target


class GuardTest(unittest.TestCase):
    def code(self, target, **kw):
        with self.assertRaises(GuardError) as cm:
            guard.check_static(target, **kw)
        return cm.exception.code

    def test_ok(self):
        guard.check_static(make_target())
        guard.check_static(make_target(url="http://localhost:8070"))
        guard.check_static(make_target(url="http://[::1]:8070"))

    def test_bad_name(self):
        self.assertEqual(self.code(make_target(db="xm")), "BAD_NAME")
        self.assertEqual(self.code(make_target(db="ofa_demox")), "BAD_NAME")
        self.assertEqual(self.code(make_target(db="ofa_demo_UPPER")), "BAD_NAME")

    def test_not_loopback(self):
        self.assertEqual(self.code(make_target(url="http://10.0.0.5:8070")), "NOT_LOOPBACK")
        self.assertEqual(self.code(make_target(url="http://127.0.0.1.evil.com:8070")), "NOT_LOOPBACK")

    def test_edition(self):
        self.assertEqual(self.code(make_target(), required_edition="community"), "EDITION_MISMATCH")

    def test_not_registered(self):
        self.assertEqual(self.code(None), "NOT_REGISTERED")

    def test_guard_error_maps_to_exit_3_through_cli(self):
        for code in ("NOT_REGISTERED", "BAD_NAME", "NOT_LOOPBACK", "MARKER_MISSING", "MARKER_MISMATCH"):
            pkg, mod = types.ModuleType("guardprobe"), types.ModuleType("guardprobe.probe")

            def register(sub, code=code):
                def handler(args):
                    raise GuardError(code)
                sub.add_parser("probe").set_defaults(func=handler)

            mod.register = register
            with mock.patch.dict(sys.modules, {"guardprobe": pkg, "guardprobe.probe": mod}):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = cli.main(["probe"], commands=("probe",), package="guardprobe")
            self.assertEqual(rc, 3, code)
            self.assertTrue(err.getvalue().startswith(f"ofa: {code}:"), err.getvalue())


class MarkerUnverifiableTest(unittest.TestCase):
    def test_key_rejected_on_marker_read_is_a_guard_refusal(self):
        # Red-team case 5: a registered demo-named DB where the key does not work.
        from ofa import client
        from tests.fakeodoo import FakeOdoo, Response, error_body
        from tests.unit.test_client import make_cfg
        with FakeOdoo(key="k", db="ofa_demo_t1") as fake:
            fake.script("ir.config_parameter", "get_str",
                        Response(401, error_body("werkzeug.exceptions.Unauthorized", "Invalid apikey")))
            with self.assertRaises(GuardError) as cm:
                client.open_client("t1", cfg=make_cfg(fake.url, key="k"))
        self.assertEqual((cm.exception.code, cm.exception.exit_code), ("MARKER_UNVERIFIABLE", 3))
