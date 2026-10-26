"""Tests for the PreToolUse guard hook. Events use the stdin shape Claude Code sends."""
import importlib.util
import io
import json
import shlex
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "ofa_guard_hook.py"
_spec = importlib.util.spec_from_file_location("ofa_guard_hook", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

NAVIGATE = "mcp__firefox-devtools__navigate_page"
NEW_PAGE = "mcp__firefox-devtools__new_page"


def bash_event(command):
    return {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command, "description": "test"}, "tool_use_id": "t"}


def nav_event(url, tool=NAVIGATE):
    return {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": {"url": url}, "tool_use_id": "t",
            "mcp_server": {"name": "firefox-devtools", "source": "user"}}


def run(stdin_text):
    err = io.StringIO()
    code = hook.main(io.StringIO(stdin_text), err)
    return code, err.getvalue()


BASH_DENY = [
    "psql -U xm -d xm",
    "PGPASSWORD=x psql -h 127.0.0.1 -U xm xm",
    "sudo -u postgres psql",
    "cd x && psql",
    "ls\npsql",
    "echo $(psql -c 1)",
    "echo `psql -c 1`",
    'echo "$(psql)"',
    'bash -c "psql"',
    "sh -c 'cd x; psql'",
    'eval "psql -l"',
    ".odoo/odoo/odoo-bin shell -d xm",
    "~/.venvs/odoo20/bin/python .odoo/odoo/odoo-bin -d xm",
    "python3 -m odoo shell",
    "docker exec odoo-pg psql",
    "curl http://127.0.0.1:8070/json/2/res.partner/search",
    "python3 -c \"import urllib.request;urllib.request.urlopen('http://localhost:8070/web/session')\"",
    "python3 -c \"import subprocess;subprocess.run(['psql'])\"",
    "wget localhost:8069/xmlrpc/2/object",
    'psql "',
    # verdict amendment 7: '#' inside a word is not a comment
    "true#; psql -l",
    "echo a#b; psql",
    # verdict amendment 8: operator-only tokens and shell keywords start a command position
    "(psql -l)",
    "{ psql -l; }",
    "if true; then psql; fi",
    "while true; do psql; done",
    "true &&\npsql",
    "true ;; psql",
    "! psql -l",
    "until false; do psql; done",
    "if false; then :; elif true; then psql; fi",
    "if false; then :; else psql; fi",
    "true |& psql",
    "f() { psql; }; f",
    # extra shapes
    "/usr/lib/postgresql/16/bin/pg_dump xm",
    "dropdb xm",
    "createdb -T ofa_tpl_20 xm2",
    "env PGHOST=127.0.0.1 psql",
    "timeout 5 psql -l",
    "nohup odoo-bin -d xm &",
    "xargs psql < dbs.txt",
    "find . -name x -exec psql {} ;",
    "p'sq'l -l",
    "ps\\\nql -l",
    "$(echo psql) -l",
    "X=psql; $X -l",
    "/usr/bin/ps?l -l",
    "echo psql | bash",
    "bash <<EOF\npsql -l\nEOF",
    "bash -lc 'psql -l'",
    "sh -c \"bash -c 'eval psql'\"",
    "cat <(psql -l)",
    "2>/dev/null psql -l",
    "> out.txt psql -l",
    "docker run --rm --network container:odoo-pg postgres psql",
    "curl \"http://localhost:80\"\"70/odoo\"",
    "curl http://127.1:8070/odoo",
    "curl -X POST https://erp.example.com/jsonrpc",
    "python3 -c 'import psycopg2; psycopg2.connect(dbname=\"xm\")'",
    "python3 -c 'import socket; socket.create_connection((\"127.0.0.1\", 8070))'",
    "node -e \"fetch('http://localhost:8070/web/session/authenticate')\"",
    "python3 -m odoo.cli shell",
    # here-documents: a shell fed a body, rule 5 on a body, unterminated body, command after the body
    "bash <<'EOF'\npsql -l\nEOF",
    "sudo bash <<EOF\nls\nEOF",
    "python3 - <<'EOF'\nimport urllib.request;urllib.request.urlopen('http://127.0.0.1:8070/json/2/x')\nEOF",
    "cat <<EOF\nx",
    "cat <<EOF\nx\nEOF\npsql -l",
    "cat <<EOF\n$(psql -l)\nEOF",
    "cat <<-EOF\n\tx\n\tEOF\npsql -l",
    "echo x # <<EOF\npsql -l\nEOF",
    "echo $((psql -l))",
]

BASH_ALLOW = [
    "ofa apply plans/x --target demo1",
    "/home/xm/odoo_functional_agent/bin/ofa doctor",
    "grep -rn psql src/",
    'git commit -m "mention psql"',
    'echo "psql; odoo-bin"',
    "ls",
    'echo "a # b"',
    "bin/ofa doctor && bin/ofa targets --json",
    "python3 -m unittest tests.hook.test_ofa_guard_hook -v 2>&1 | tail -5",
    "git log --oneline | head",
    "ls -la > /tmp/x 2>&1",
    "[ -f x ] && echo yes",
    "bash scripts/build.sh",
    "curl -s https://www.odoo.com/documentation/20.0/",
    "docker ps",
    # here-documents: the body is data
    "git commit -q -F - <<'EOF'\n[ADD] x: y\n\nUse psql only via ofa.\nEOF",
    "cat > notes.txt <<'EOF'\npsql is mentioned here\nEOF",
    "cat > notes.md <<'EOF'\nRun `psql` never; use $(ofa) docs.\nEOF",
    "cat <<<'psql -l' | wc -c",
    "echo $((1 << 2))",
]

NAV_DENY = [
    "https://acme.odoo.com/odoo/action-1",
    "https://erp.example.com/",
    "https://erp.example.com/app",
    "https://www.odoo.com/odoo/action-1",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "http://127.0.0.1@erp.example.com/",
    "http://localhost.example.com/",
    "https://www.odoo.com/documentation/../odoo/action-1",
    "https://www.odoo.com/documentation/%2e%2e/odoo/action-1",
    "http://erp.example.com\\@127.0.0.1/",
    "http:erp.example.com",
    "",
]

NAV_ALLOW = [
    "http://127.0.0.1:8070/odoo/sale.order/1",
    "https://www.odoo.com/documentation/20.0/",
    "about:blank",
    "http://localhost:8070/odoo",
    "http://[::1]:8070/odoo",
    "https://github.com/odoo/odoo/blob/20.0/addons/sale/models/sale_order.py",
]


class BashRulesTest(unittest.TestCase):
    def test_deny(self):
        for cmd in BASH_DENY:
            with self.subTest(cmd=cmd):
                code, err = run(json.dumps(bash_event(cmd)))
                self.assertEqual(code, 2)
                self.assertTrue(err.startswith("ofa guard: "))
                self.assertEqual(err.count("\n"), 1)

    def test_allow(self):
        for cmd in BASH_ALLOW:
            with self.subTest(cmd=cmd):
                self.assertEqual(run(json.dumps(bash_event(cmd))), (0, ""))

    def test_recursion_depth_cap(self):
        def nested(cmd, levels):
            for _ in range(levels):
                cmd = "bash -c " + shlex.quote(cmd)
            return cmd
        code, err = run(json.dumps(bash_event(nested("psql", 3))))
        self.assertEqual(code, 2)
        self.assertIn("psql runs against", err)
        self.assertEqual(run(json.dumps(bash_event(nested("ls", 5)))), (0, ""))
        code, err = run(json.dumps(bash_event(nested("ls", 6))))
        self.assertEqual(code, 2)
        self.assertIn("nesting deeper than 5", err)

    def test_unbalanced_quote_is_internal_error(self):
        code, err = run(json.dumps(bash_event('psql "')))
        self.assertEqual(code, 2)
        self.assertIn("internal error, denying (ValueError)", err)


class NavigationRuleTest(unittest.TestCase):
    def test_deny(self):
        for tool in (NAVIGATE, NEW_PAGE):
            for url in NAV_DENY:
                with self.subTest(tool=tool, url=url):
                    code, err = run(json.dumps(nav_event(url, tool)))
                    self.assertEqual(code, 2)
                    self.assertTrue(err.startswith("ofa guard: "))

    def test_allow(self):
        for tool in (NAVIGATE, NEW_PAGE):
            for url in NAV_ALLOW:
                with self.subTest(tool=tool, url=url):
                    self.assertEqual(run(json.dumps(nav_event(url, tool))), (0, ""))

    def test_new_page_cases_from_task(self):
        self.assertEqual(run(json.dumps(nav_event("https://erp.example.com/", NEW_PAGE)))[0], 2)
        self.assertEqual(run(json.dumps(nav_event("http://127.0.0.1:8070/odoo", NEW_PAGE))), (0, ""))


EVALUATE = "mcp__firefox-devtools__evaluate_script"
SCRIPT_DENY = [
    "() => { location.href = 'https://erp.example.com/' }",
    "() => window.location.assign('https://erp.example.com/')",
    "() => document.location = 'https://x.example/'",
    "() => window.open('https://erp.example.com/')",
    "() => fetch('https://erp.example.com/api')",
    "() => { const x = new XMLHttpRequest(); }",
    "() => navigator.sendBeacon('https://x.example/', 'd')",
    "() => new WebSocket('wss://x.example/')",
    "() => import('https://x.example/m.js')",
    "() => history.pushState({}, '', '/x')",
    "() => document.forms[0].submit()",
    "() => document.querySelector('a').click()",
    "() => { document.querySelector('img').src = 'https://x.example/p.png' }",
    "() => window['loc' + 'ation'].href",
    "() => globalThis['fe' + 'tch']('https://x.example/')",
    "() => eval('loc' + 'ation')",
    "() => Function('return this')()",
    "() => '\\u006cocation'",
]
SCRIPT_ALLOW = [
    "() => new Promise(r => requestAnimationFrame(() => r(true)))",
    "() => document.title",
    "() => document.querySelector('input[name=\"name\"]').value",
    "() => document.visibilityState",
    "() => Array.from(document.querySelectorAll('.o_field_widget')).length",
]


class ScriptRuleTest(unittest.TestCase):
    """Red-team case 8: in-page navigation through evaluate_script."""

    def event(self, fn):
        return json.dumps({"tool_name": EVALUATE, "tool_input": {"function": fn}})

    def test_deny(self):
        for fn in SCRIPT_DENY:
            with self.subTest(fn=fn):
                code, err = run(self.event(fn))
                self.assertEqual(code, 2)
                self.assertTrue(err.startswith("ofa guard: "))

    def test_allow(self):
        for fn in SCRIPT_ALLOW:
            with self.subTest(fn=fn):
                self.assertEqual(run(self.event(fn)), (0, ""))

    def test_missing_function_fails_closed(self):
        self.assertEqual(run(json.dumps({"tool_name": EVALUATE, "tool_input": {}}))[0], 2)


class FailClosedTest(unittest.TestCase):
    def assert_internal_error(self, stdin_text):
        code, err = run(stdin_text)
        self.assertEqual(code, 2)
        self.assertRegex(err, r"^ofa guard: internal error, denying \(\w+\)\n$")

    def test_not_json(self):
        self.assert_internal_error("not json")

    def test_missing_tool_input(self):
        self.assert_internal_error('{"tool_name":"Bash"}')

    def test_missing_command(self):
        self.assert_internal_error('{"tool_name":"Bash","tool_input":{}}')

    def test_missing_url(self):
        self.assert_internal_error(json.dumps({"tool_name": NAVIGATE, "tool_input": {}}))

    def test_non_string_command(self):
        self.assert_internal_error('{"tool_name":"Bash","tool_input":{"command":["psql"]}}')

    def test_injected_exception(self):
        with mock.patch.object(hook, "check_bash", side_effect=RuntimeError("boom")):
            code, err = run(json.dumps(bash_event("ls")))
        self.assertEqual(code, 2)
        self.assertEqual(err, "ofa guard: internal error, denying (RuntimeError)\n")

    def test_unexpected_tool(self):
        code, err = run(json.dumps({"tool_name": "Write", "tool_input": {}}))
        self.assertEqual(code, 2)
        self.assertIn("unexpected tool", err)


class ScriptTest(unittest.TestCase):
    """The file runs as a script, the way Claude Code invokes it."""

    def run_script(self, stdin_text):
        return subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True)

    def test_garbage_exits_2(self):
        p = self.run_script("garbage")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, "")

    def test_deny_and_allow(self):
        self.assertEqual(self.run_script(json.dumps(bash_event("psql -l"))).returncode, 2)
        p = self.run_script(json.dumps(bash_event("ls")))
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))


class HooksJsonTest(unittest.TestCase):
    def test_handlers(self):
        data = json.loads((HOOK.parent / "hooks.json").read_text())
        entries = data["hooks"]["PreToolUse"]
        self.assertEqual({e["matcher"] for e in entries}, {"Bash", f"{NAVIGATE}|{NEW_PAGE}|{EVALUATE}"})
        for e in entries:
            for h in e["hooks"]:
                self.assertEqual(h["type"], "command")
                self.assertEqual(h["timeout"], 10)
                self.assertEqual(h["onFailure"], "block")
                self.assertEqual(h["command"], 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/ofa_guard_hook.py"')


if __name__ == "__main__":
    unittest.main()
