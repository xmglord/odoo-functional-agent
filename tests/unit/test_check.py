"""ofa-check: the read-only report the help skill runs."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from ofa import ROOT, check, cli

BIN = ROOT / "bin" / "ofa-check"
SKILL = ROOT / "skills" / "help" / "SKILL.md"
CONFIG = """[server]
url = "http://127.0.0.1:1"
"""
SERVER = """[server]
odoo_bin = "/nonexistent/odoo-bin"
python = "/nonexistent/python"
odoo_conf = "{conf}"
url = "http://127.0.0.1:1"
odoo_version = "20.0"
edition = "community"
template_db = "ofa_tpl_20"
template_modules = ["crm"]
log_file = "/nonexistent/odoo.log"
xmlid_store = "ir_model_data"
"""
HARDENED = "[options]\ndb_user = demo\ndbfilter = ^ofa_demo_.*$\nmax_cron_threads = 0\nlist_db = False\n"


def snapshot(directory):
    return sorted((str(p), p.stat().st_mtime_ns) for p in Path(directory).rglob("*"))


class CheckTest(unittest.TestCase):
    def run_check(self, config_dir):
        env = dict(os.environ, OFA_CONFIG_DIR=str(config_dir))
        return subprocess.run([str(BIN)], capture_output=True, text=True, env=env)

    def test_runs_only_read_only_commands(self):
        self.assertEqual(check.CHECKS, (("doctor",), ("server", "status"), ("targets",)))
        parser = cli.build_parser()
        for argv in check.CHECKS:
            self.assertIn("func", vars(parser.parse_args(list(argv))))

    def test_missing_config_is_reported_under_each_section(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.run_check(d)
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stderr, "")
            self.assertEqual(re.findall(r"^== ofa (.+)$", p.stdout, re.M), ["doctor", "server status", "targets"])
            self.assertEqual(p.stdout.count("CONFIG_MISSING"), 3)
            self.assertEqual(snapshot(d), [])

    def test_changes_nothing_in_the_config_dir(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "config.toml").write_text(CONFIG)
            before = snapshot(d)
            self.run_check(d)
            self.assertEqual(snapshot(d), before)


class DoctorTemplateTest(unittest.TestCase):
    """The template line comes from a read of pg_database, faked here with a psql on PATH."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        conf = d / "odoo20.conf"
        conf.write_text(HARDENED)
        (d / "config.toml").write_text(SERVER.format(conf=conf))
        self.fake = d / "psql"
        self.env = dict(os.environ, OFA_CONFIG_DIR=str(d), PATH=f"{d}:{os.environ['PATH']}")

    def doctor(self, psql_body):
        self.fake.write_text("#!/bin/sh\n" + psql_body + "\n")
        self.fake.chmod(0o755)
        p = subprocess.run([str(ROOT / "bin" / "ofa"), "doctor"], capture_output=True, text=True, env=self.env)
        return next(l for l in p.stdout.splitlines() if "template database" in l)

    def test_found(self):
        self.assertEqual(self.doctor("echo 1"), "OK\ttemplate database\tofa_tpl_20")

    def test_not_found(self):
        self.assertEqual(self.doctor("exit 0"), "FAIL\ttemplate database\tofa_tpl_20 not found")

    def test_postgres_unreachable(self):
        self.assertIn("PG_ERROR", self.doctor("echo 'connection refused' >&2; exit 2"))

    def test_query_only_reads_pg_database(self):
        log = Path(self.tmp.name, "calls")
        self.doctor(f'printf "%s\\n" "$*" > {log}; echo 1')
        self.assertIn("SELECT 1 FROM pg_database WHERE datname = 'ofa_tpl_20'", log.read_text())


class HelpSkillTest(unittest.TestCase):
    def test_runs_ofa_check_and_declares_no_allowed_tools(self):
        text = SKILL.read_text()
        self.assertIn("Run `ofa-check`, then `ss -tln", text)
        # allowed-tools makes the Skill call itself need permission: in `claude -p` it returned no instructions.
        self.assertNotIn("allowed-tools", text)


if __name__ == "__main__":
    unittest.main()
