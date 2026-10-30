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


class HelpSkillTest(unittest.TestCase):
    def test_runs_ofa_check_and_declares_no_allowed_tools(self):
        text = SKILL.read_text()
        self.assertIn("Run `ofa-check`, then `ss -tln", text)
        # allowed-tools makes the Skill call itself need permission: in `claude -p` it returned no instructions.
        self.assertNotIn("allowed-tools", text)


if __name__ == "__main__":
    unittest.main()
