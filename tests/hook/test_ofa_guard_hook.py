"""Tests for the PreToolUse guard hook. Events use the stdin shape Claude Code sends."""
import importlib.util
import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "ofa_guard_hook.py"
_spec = importlib.util.spec_from_file_location("ofa_guard_hook", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

NAVIGATE = "mcp__firefox-devtools__navigate_page"
NEW_PAGE = "mcp__firefox-devtools__new_page"


def setUpModule():
    """The rule tests run in an active session: session "s" has its marker."""
    global DATA_DIR, env_patch
    DATA_DIR = tempfile.mkdtemp()
    os.mkdir(os.path.join(DATA_DIR, "active_sessions"))
    Path(DATA_DIR, "active_sessions", "s").touch()
    env_patch = mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": DATA_DIR})
    env_patch.start()


def tearDownModule():
    env_patch.stop()
    shutil.rmtree(DATA_DIR)


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
        return json.dumps({"session_id": "s", "tool_name": EVALUATE, "tool_input": {"function": fn}})

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
        self.assertEqual(run(json.dumps({"session_id": "s", "tool_name": EVALUATE, "tool_input": {}}))[0], 2)


class FailClosedTest(unittest.TestCase):
    def assert_internal_error(self, stdin_text):
        code, err = run(stdin_text)
        self.assertEqual(code, 2)
        self.assertRegex(err, r"^ofa guard: internal error, denying \(\w+\)\n$")

    def test_missing_tool_input(self):
        self.assert_internal_error('{"session_id":"s","tool_name":"Bash"}')

    def test_missing_command(self):
        self.assert_internal_error('{"session_id":"s","tool_name":"Bash","tool_input":{}}')

    def test_missing_url(self):
        self.assert_internal_error(json.dumps({"session_id": "s", "tool_name": NAVIGATE, "tool_input": {}}))

    def test_non_string_command(self):
        self.assert_internal_error('{"session_id":"s","tool_name":"Bash","tool_input":{"command":["psql"]}}')

    def test_injected_exception(self):
        with mock.patch.object(hook, "check_bash", side_effect=RuntimeError("boom")):
            code, err = run(json.dumps(bash_event("ls")))
        self.assertEqual(code, 2)
        self.assertEqual(err, "ofa guard: internal error, denying (RuntimeError)\n")

    def test_unexpected_tool(self):
        code, err = run(json.dumps({"session_id": "s", "tool_name": "Write", "tool_input": {}}))
        self.assertEqual(code, 2)
        self.assertIn("unexpected tool", err)


class ScriptTest(unittest.TestCase):
    """The file runs as a script, the way Claude Code invokes it."""

    def run_script(self, stdin_text):
        return subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True)

    def test_garbage_exits_0(self):
        p = self.run_script("garbage")
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))

    def test_deny_and_allow(self):
        self.assertEqual(self.run_script(json.dumps(bash_event("psql -l"))).returncode, 2)
        p = self.run_script(json.dumps(bash_event("ls")))
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))


class SessionScopeTest(unittest.TestCase):
    """Marker lifecycle, against a data directory of its own."""

    def setUp(self):
        self.data = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.data)
        patcher = mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": self.data})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.marker = Path(self.data, "active_sessions", "new")

    def event(self, **extra):
        return {"session_id": "new", "hook_event_name": "PreToolUse", **extra}

    def bash(self, command):
        return self.event(tool_name="Bash", tool_input={"command": command})

    def prompt(self, text):
        return {"session_id": "new", "hook_event_name": "UserPromptSubmit", "prompt": text}

    def test_inactive_allows_every_rule_target(self):
        for command in ["psql -l", ".odoo/odoo/odoo-bin -d x", "docker exec odoo-pg psql", "curl localhost:8069/web/login",
                        "pg_dump x", "cat 'unbalanced"]:
            with self.subTest(command=command):
                self.assertEqual(run(json.dumps(self.bash(command))), (0, ""))
        nav = self.event(tool_name=NAVIGATE, tool_input={"url": "about:home"})
        self.assertEqual(run(json.dumps(nav)), (0, ""))
        script = self.event(tool_name=EVALUATE, tool_input={"function": "() => document.body.click()"})
        self.assertEqual(run(json.dumps(script)), (0, ""))
        self.assertFalse(self.marker.exists())

    def test_inactive_errors_exit_0(self):
        for text in ["garbage", "", "[]", "null", "{}", '{"session_id":"new"}', '{"tool_name":"Bash"}',
                     '{"session_id":"new","hook_event_name":"PreToolUse","tool_name":"Bash"}',
                     '{"session_id":"new","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":[1]}}',
                     '{"session_id":"../x","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"psql"}}',
                     '{"session_id":7,"tool_name":"Bash"}', '{"hook_event_name":"PreToolUse","tool_name":"Bash"}']:
            with self.subTest(text=text):
                self.assertEqual(run(text), (0, ""))

    def test_no_data_dir_inactive_exits_0(self):
        with mock.patch.dict(os.environ):
            del os.environ["CLAUDE_PLUGIN_DATA"]
            self.assertEqual(run(json.dumps(self.bash("psql -l"))), (0, ""))

    def test_unexpected_exception_in_inactive_session_exits_0(self):
        with mock.patch.object(hook, "marker_path", side_effect=RuntimeError("boom")):
            self.assertEqual(run(json.dumps(self.bash("psql -l"))), (0, ""))
        with mock.patch.object(hook, "is_activating", side_effect=RuntimeError("boom")):
            self.assertEqual(run(json.dumps(self.bash("psql -l"))), (0, ""))

    def test_skill_activates(self):
        for skill in ["odoo-functional-agent:odoo-functional", "odoo-functional-agent:odoo-explain"]:
            with self.subTest(skill=skill):
                self.marker.unlink(missing_ok=True)
                self.assertEqual(run(json.dumps(self.event(tool_name="Skill", tool_input={"skill": skill}))), (0, ""))
                self.assertTrue(self.marker.exists())

    def test_other_skill_does_not_activate(self):
        event = self.event(tool_name="Skill", tool_input={"skill": "other:odoo-functional"})
        self.assertEqual(run(json.dumps(event)), (0, ""))
        self.assertFalse(self.marker.exists())

    def test_help_does_not_activate(self):
        help_skill = self.event(tool_name="Skill", tool_input={"skill": "odoo-functional-agent:help"})
        for event in [help_skill, self.prompt("/odoo-functional-agent:help"), self.bash("ofa-check"),
                      self.bash("/repo/bin/ofa-check"), self.bash("ofa-check 2>&1 | head -5")]:
            with self.subTest(event=event):
                self.assertEqual(run(json.dumps(event)), (0, ""))
                self.assertFalse(self.marker.exists())
        self.assertEqual(run(json.dumps(self.bash("psql --version"))), (0, ""))

    def test_readonly_ofa_commands_still_activate(self):
        for command in ["ofa doctor", "ofa server status", "ofa targets"]:
            with self.subTest(command=command):
                self.marker.unlink(missing_ok=True)
                run(json.dumps(self.bash(command)))
                self.assertTrue(self.marker.exists())
                self.assertEqual(run(json.dumps(self.bash("psql -l")))[0], 2)

    def test_ofa_command_activates(self):
        for command in ["ofa status", "cd x && ofa apply y", "/repo/bin/ofa server status", "sudo ofa x",
                        "bash -c 'ofa x'", "echo $(ofa x)", "ofa x; cat 'unbalanced"]:
            with self.subTest(command=command):
                self.marker.unlink(missing_ok=True)
                run(json.dumps(self.bash(command)))
                self.assertTrue(self.marker.exists())

    def test_ofa_word_outside_command_position_does_not_activate(self):
        for command in ["grep ofa README.md", "git commit -m 'ofa fix'", "ls src/ofa", "cat sofa.txt"]:
            with self.subTest(command=command):
                self.assertEqual(run(json.dumps(self.bash(command))), (0, ""))
                self.assertFalse(self.marker.exists())

    def test_activating_command_is_itself_checked(self):
        code, err = run(json.dumps(self.bash("ofa status; psql -l")))
        self.assertEqual(code, 2)
        self.assertIn("psql", err)
        self.assertTrue(self.marker.exists())

    def test_prompt_activates(self):
        for text in ["Need this.\n\nTarget: partner\n", "target:partner", "  TARGET : x",
                     "/odoo-functional-agent:odoo-functional set up sales", "/odoo-functional-agent:odoo-explain why"]:
            with self.subTest(text=text):
                self.marker.unlink(missing_ok=True)
                self.assertEqual(run(json.dumps(self.prompt(text))), (0, ""))
                self.assertTrue(self.marker.exists())

    def test_other_prompts_do_not_activate(self):
        for text in ["what is the target: market", "Target:", "Target:\n\nnext", "no marker here"]:
            with self.subTest(text=text):
                self.assertEqual(run(json.dumps(self.prompt(text))), (0, ""))
                self.assertFalse(self.marker.exists())

    def test_active_session_stays_active_and_denies(self):
        run(json.dumps(self.prompt("Target: x")))
        code, err = run(json.dumps(self.bash("psql -l")))
        self.assertEqual(code, 2)
        self.assertEqual(run(json.dumps(self.prompt("next question"))), (0, ""))
        self.assertEqual(run(json.dumps(self.event(tool_name="Skill", tool_input={"skill": "other:x"}))), (0, ""))

    def test_subagent_event_shares_the_session(self):
        run(json.dumps(self.prompt("Target: x")))
        event = self.bash("psql -l")
        event["agent_id"] = "a73b"
        self.assertEqual(run(json.dumps(event))[0], 2)

    def test_active_errors_deny(self):
        run(json.dumps(self.prompt("Target: x")))
        self.assertEqual(run('{"session_id":"new","hook_event_name":"PreToolUse","tool_name":"Bash"}')[0], 2)
        self.assertEqual(run(json.dumps(self.bash("cat 'unbalanced")))[0], 2)

    def test_activation_failure_denies(self):
        Path(self.data, "active_sessions").write_text("a file, so the marker cannot be created")
        code, err = run(json.dumps(self.bash("ofa status")))
        self.assertEqual(code, 2)
        self.assertIn("internal error", err)

    def test_activation_without_session_id_denies(self):
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ofa status"}}
        self.assertEqual(run(json.dumps(event))[0], 2)

    def test_denying_leaves_the_marker_in_place(self):
        run(json.dumps(self.prompt("Target: x")))
        self.assertEqual(run(json.dumps(self.bash("psql -l")))[0], 2)
        self.assertTrue(self.marker.exists())

    def test_use_refreshes_the_marker(self):
        run(json.dumps(self.prompt("Target: x")))
        os.utime(self.marker, (1, 1))
        run(json.dumps(self.bash("ls")))
        self.assertGreater(self.marker.stat().st_mtime, 1)

    def test_age_limit_matches_transcript_retention(self):
        self.assertEqual(hook.MARKER_MAX_AGE_SECONDS, 30 * 86400)

    def test_markers_are_off_limits_in_active_session(self):
        run(json.dumps(self.prompt("Target: x")))
        for command in ["rm ~/.claude/plugins/data/x/active_sessions/new", "rm -r $CLAUDE_PLUGIN_DATA", "ls ~/.claude/plugins/data",
                        'rm "$HOME/.claude/plugins/data/x/active_""sessions/new"', "cat <<'EOF' > x\nactive_sessions\nEOF"]:
            with self.subTest(command=command):
                code, err = run(json.dumps(self.bash(command)))
                self.assertEqual(code, 2)

    def test_old_markers_are_pruned(self):
        directory = Path(self.data, "active_sessions")
        directory.mkdir()
        old = directory / "old"
        old.touch()
        os.utime(old, (1, 1))
        run(json.dumps(self.prompt("Target: x")))
        self.assertFalse(old.exists())
        self.assertTrue(self.marker.exists())


class WrapperTest(unittest.TestCase):
    """hooks/ofa_guard.sh when the Python guard cannot give an answer."""

    def setUp(self):
        self.data = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.data)
        Path(self.data, "active_sessions").mkdir()
        self.bin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.bin)

    def fake_python(self, body):
        path = Path(self.bin, "python3")
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def run_wrapper(self, event, path=None):
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=self.data, PATH=path or f"{self.bin}:{os.environ['PATH']}")
        text = event if isinstance(event, str) else json.dumps(event)
        return subprocess.run(["/bin/sh", str(HOOK.parent / "ofa_guard.sh")], input=text, capture_output=True,
                              text=True, env=env).returncode

    def activate(self):
        Path(self.data, "active_sessions", "s").touch()

    def test_decisions_pass_through(self):
        self.activate()
        self.assertEqual(self.run_wrapper(bash_event("psql -l"), path=os.environ["PATH"]), 2)
        self.assertEqual(self.run_wrapper(bash_event("ls"), path=os.environ["PATH"]), 0)

    def test_python_crash(self):
        self.fake_python("exit 1")
        self.assertEqual(self.run_wrapper(bash_event("psql -l")), 0)
        self.assertEqual(self.run_wrapper("garbage"), 0)
        self.activate()
        self.assertEqual(self.run_wrapper(bash_event("ls")), 2)

    def test_python_missing(self):
        tools = Path(self.bin)
        for name in ("sed", "head", "grep", "dirname", "cat"):
            (tools / name).symlink_to(shutil.which(name))
        self.assertEqual(self.run_wrapper(bash_event("psql -l"), path=str(tools)), 0)
        self.activate()
        self.assertEqual(self.run_wrapper(bash_event("ls"), path=str(tools)), 2)

    def test_ofa_check_is_not_activating_when_python_cannot_run(self):
        self.fake_python("exit 1")
        self.assertEqual(self.run_wrapper(bash_event("ofa-check")), 0)
        self.assertEqual(self.run_wrapper(bash_event("/repo/bin/ofa-check")), 0)

    def test_python_hang(self):
        self.fake_python("exit 124")  # what timeout(1) returns when it kills python
        self.assertEqual(self.run_wrapper(bash_event("ls")), 0)

    def test_activating_events_deny_when_python_cannot_run(self):
        self.fake_python("exit 1")
        self.assertEqual(self.run_wrapper(bash_event("ofa status")), 2)
        skill = {"session_id": "n", "hook_event_name": "PreToolUse", "tool_name": "Skill",
                 "tool_input": {"skill": "odoo-functional-agent:odoo-functional"}}
        self.assertEqual(self.run_wrapper(skill), 2)
        prompt = {"session_id": "n", "hook_event_name": "UserPromptSubmit", "prompt": "x\nTarget: y"}
        self.assertEqual(self.run_wrapper(prompt), 2)
        self.assertEqual(self.run_wrapper(dict(prompt, prompt="ordinary")), 0)


class HooksJsonTest(unittest.TestCase):
    def handlers(self):
        return json.loads((HOOK.parent / "hooks.json").read_text())["hooks"]

    def test_handlers(self):
        hooks = self.handlers()
        self.assertEqual(set(hooks), {"PreToolUse", "UserPromptSubmit"})
        self.assertEqual({e["matcher"] for e in hooks["PreToolUse"]}, {"Bash", "Skill", f"{NAVIGATE}|{NEW_PAGE}|{EVALUATE}"})
        for entries in hooks.values():
            for e in entries:
                for h in e["hooks"]:
                    self.assertEqual(h["type"], "command")
                    self.assertEqual(h["timeout"], 10)
                    self.assertEqual(h["onFailure"], "block")
                    self.assertIn("ofa_guard.sh", h["command"])

    def run_command(self, root, data, event):
        command = self.handlers()["PreToolUse"][0]["hooks"][0]["command"].replace("${CLAUDE_PLUGIN_ROOT}", root)
        command = command.replace("${CLAUDE_PLUGIN_DATA}", data)
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=root, CLAUDE_PLUGIN_DATA=data)
        return subprocess.run(["/bin/sh", "-c", command], input=json.dumps(event), text=True, capture_output=True, env=env)

    def test_runs_the_wrapper(self):
        self.assertEqual(self.run_command(str(HOOK.parents[1]), DATA_DIR, bash_event("psql -l")).returncode, 2)

    def test_plugin_files_gone(self):
        with tempfile.TemporaryDirectory() as gone:
            self.assertEqual(self.run_command(gone, DATA_DIR, bash_event("ls")).returncode, 2)
            inactive = dict(bash_event("ls"), session_id="other")
            self.assertEqual(self.run_command(gone, DATA_DIR, inactive).returncode, 0)


if __name__ == "__main__":
    unittest.main()
