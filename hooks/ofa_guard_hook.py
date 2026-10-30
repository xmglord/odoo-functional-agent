#!/usr/bin/env python3
"""PreToolUse guard hook (layer b of the demo-only guard).

Reads the Claude Code hook event JSON on stdin. Installed plugins run this for
every session on the machine, so it does nothing until the session uses the
agent: invoking the odoo-functional or odoo-explain skill, running `ofa`, or a
prompt with a `Target:` line activates it, and a marker file keeps it active for
that session. The help skill and `ofa-check` do not: asking for help is not using
the agent. `/clear` starts a new session id in the same process, so SessionEnd and
SessionStart hand the marker over to it.

In an active session it denies (exit 2, one line on stderr) Bash commands that
reach Postgres or an Odoo server without going through `ofa`, and browser
navigation to anything but the local demo server or a short documentation
allowlist. Allows with exit 0 and no output.

Fails closed only in an active session or on an activating event: there any
parse error, missing field or unexpected exception exits 2. Anywhere else an
error exits 0, because it must not block sessions that never used the agent.
Stdlib only. See docs/guard.md for the rules and the known gaps.
"""
import json
import os
import re
import shlex
import sys
import time
from urllib.parse import unquote, urlsplit

MAX_DEPTH = 5

BASH_TOOL = "Bash"
NAV_TOOLS = frozenset({"mcp__firefox-devtools__navigate_page", "mcp__firefox-devtools__new_page"})
SCRIPT_TOOL = "mcp__firefox-devtools__evaluate_script"
SKILL_TOOL = "Skill"

# What makes a session an agent session. The marker lives under the plugin's data directory.
ACTIVATING_SKILLS = frozenset({"odoo-functional-agent:odoo-functional", "odoo-functional-agent:odoo-explain"})
ACTIVATING_PROMPT_RE = re.compile(
    r"^[ \t]*(?:target[ \t]*:[ \t]*\S|/odoo-functional-agent:odoo-(?:functional|explain)\b)", re.I | re.M
)
OFA_WORD_RE = re.compile(r"(?<![\w.-])ofa(?![\w.-])")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MARKER_DIR = "active_sessions"
# Claude Code's default transcript retention (cleanupPeriodDays): an older session cannot be resumed.
MARKER_MAX_AGE_SECONDS = 30 * 86400
# A Bash command may not touch the markers: that would switch the guard off from inside the session.
MARKER_ACCESS_RE = re.compile(MARKER_DIR + r"|plugins/data|CLAUDE_PLUGIN_DATA")
# /clear: SessionEnd leaves clear.<CLAUDE_PID> beside the markers (the dot keeps it from being a session id) and
# SessionStart, about 60 ms later, turns it into the new id's marker. CLAUDE_PID is the same across both events.
SESSION_EVENTS = frozenset({"SessionEnd", "SessionStart"})
CLAUDE_PID_RE = re.compile(r"^[0-9]{1,10}$")
CLEAR_HANDOFF_MAX_AGE_SECONDS = 60

# In-page JavaScript must never navigate or talk to the network: that would reach
# any host without going through the navigation rule. ofa's own scripts (render
# probes, reading field values) need none of this. Computed access to globals and
# dynamic code are denied too, since they are the obvious way to spell these.
SCRIPT_DENY = re.compile(
    r"\blocation\b|\bhref\b|\bopen\s*\(|\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource"
    r"|\bimport\s*\(|\bhistory\b|\bsubmit\s*\(|\.click\s*\(|document\.write|\bsrc\s*="
    r"|\b(?:window|self|globalThis|top|parent|frames|document)\s*\[|\beval\s*\(|\bFunction\s*\(|\bsetTimeout\s*\(\s*['\"`]"
    r"|\\u|\\x"
)

# (host, path prefix) pairs a browser tool may open besides the loopback demo server.
NAV_ALLOWLIST = (
    ("www.odoo.com", "/documentation/"),
    ("github.com", "/odoo/"),
)
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# Command words that reach Postgres or start an Odoo server directly.
DB_COMMANDS = frozenset({
    "psql", "pg_dump", "pg_dumpall", "pg_restore", "dropdb", "createdb", "odoo-bin", "odoo",
    "pgcli", "vacuumdb", "reindexdb", "clusterdb", "createuser", "dropuser",
})
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "mksh", "fish", "tcsh", "csh"})
# Prefixes that run the next word as a command; skipped before the command word.
PREFIXES = frozenset({"sudo", "doas", "env", "nohup", "time", "exec", "command", "builtin", "xargs",
                      "nice", "ionice", "timeout", "stdbuf", "setsid", "chrt", "taskset", "unbuffer",
                      "watch", "coproc", "su", "script", "ssh", "busybox", "flock", "strace", "ltrace"})
NETWORK = frozenset({"curl", "wget", "http", "https", "nc", "ncat", "netcat", "socat", "telnet"})
INTERPRETERS = frozenset({"node", "nodejs", "deno", "bun", "perl", "ruby", "php", "lua", "awk", "gawk", "mawk"})
PYTHON_RE = re.compile(r"^python[0-9.]*$")
FIND_EXEC = frozenset({"-exec", "-execdir", "-ok", "-okdir"})

# Shell syntax that starts a new command position (verdict amendment 8).
KEYWORD_SEPARATORS = frozenset({"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until"})
PUNCT = "();<>|&\n"
SEP_CHARS = frozenset(";|&\n()")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=")
DYNAMIC_RE = re.compile(r"[$`*?\[]|\{.*[,.]")
LINE_CONTINUATION_RE = re.compile(r"(?<!\\)((?:\\\\)*)\\\n")

# Any host, not only loopback, on the Odoo port range or the Postgres port: loopback has too
# many spellings (127.1, 0, [::ffff:127.0.0.1], 2130706433) to enumerate safely.
RAW_ODOO_RE = re.compile(r"/json/2/|/jsonrpc|/xmlrpc|/web/|:(?:80[6-9]\d|5432)(?!\d)")
RAW_INTERPRETER_RE = re.compile(
    r"(?<![\w-])(?:psql|pg_dump|pg_dumpall|pg_restore|createdb|dropdb|odoo-bin)(?![\w-])"
    r"|\b(?:psycopg2?|asyncpg|pg8000)\b|\bimport\s+odoo\b|\bfrom\s+odoo\b"
    r"|(?<![\w.])(?:80[6-9]\d|5432)(?![\w.])"
)


class Deny(Exception):
    """A rule matched; the message is the reason shown to the model."""


# ---------------------------------------------------------------- Bash rules

def tokenize(cmd):
    """Quote-aware tokens. Comments are not stripped (a `#` inside a word is literal)."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def is_redirect(tok):
    return bool(tok) and set(tok) <= set("<>&") and ("<" in tok or ">" in tok)


def is_separator(tok):
    if tok in KEYWORD_SEPARATORS:
        return True
    return bool(tok) and set(tok) <= set(PUNCT) and not is_redirect(tok) and bool(set(tok) & SEP_CHARS)


def split_segments(tokens):
    segments, cur = [], []
    for tok in tokens:
        if is_separator(tok):
            if cur:
                segments.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        segments.append(cur)
    return segments


HEREDOC_WORD_END = frozenset(" \t\n;&|()<>")


def _skip_arith(cmd, i):
    """Index just past the `$((...))` starting at i."""
    depth, j = 0, i + 1
    while j < len(cmd):
        depth += {"(": 1, ")": -1}.get(cmd[j], 0)
        j += 1
        if depth == 0:
            return j
    raise ValueError("unbalanced arithmetic expansion")


def split_heredocs(cmd):
    """Remove here-document bodies from `cmd`.

    Returns (cmd without bodies, [(body, delimiter_was_quoted), ...]). Recognises `<<WORD`, `<<'WORD'`,
    `<<"WORD"` and `<<-WORD` outside quotes and comments; `<<<` here-strings are left alone. A body runs
    from the end of the line that holds the operator to a line equal to WORD (tabs stripped for `<<-`).
    An unterminated body raises ValueError, which the hook turns into a deny.
    """
    out, bodies, pending = [], [], []
    i, n = 0, len(cmd)
    quote = None
    while i < n:
        c = cmd[i]
        if quote == "'":
            out.append(c)
            quote = None if c == "'" else quote
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if quote == '"':
            out.append(c)
            quote = None if c == '"' else quote
            i += 1
            continue
        if c in "'\"":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "#" and (i == 0 or cmd[i - 1] in " \t\n;&|()"):
            j = cmd.find("\n", i)
            j = n if j < 0 else j
            out.append(cmd[i:j])
            i = j
            continue
        if cmd.startswith("$((", i):
            j = _skip_arith(cmd, i)
            out.append(cmd[i:j])
            i = j
            continue
        if cmd.startswith("<<<", i):
            out.append("<<<")
            i += 3
            continue
        if cmd.startswith("<<", i):
            j = i + 2
            strip_tabs = j < n and cmd[j] == "-"
            j += strip_tabs
            while j < n and cmd[j] in " \t":
                j += 1
            k, word, quoted, q = j, [], False, None
            while k < n and (q or cmd[k] not in HEREDOC_WORD_END):
                ch = cmd[k]
                if q:
                    if ch == q:
                        q = None
                    else:
                        word.append(ch)
                elif ch in "'\"":
                    q, quoted = ch, True
                elif ch == "\\" and k + 1 < n:
                    quoted = True
                    word.append(cmd[k + 1])
                    k += 1
                else:
                    word.append(ch)
                k += 1
            if q or not word:
                raise ValueError("bad here-document delimiter")
            pending.append(("".join(word), strip_tabs, quoted))
            out.append(cmd[i:k])
            i = k
            continue
        if c == "\n" and pending:
            out.append(c)
            i += 1
            for delim, strip_tabs, quoted in pending:
                lines = []
                while True:
                    if i >= n:
                        raise ValueError(f"unterminated here-document {delim!r}")
                    j = cmd.find("\n", i)
                    j = n if j < 0 else j
                    line = cmd[i:j]
                    i = j + 1
                    if (line.lstrip("\t") if strip_tabs else line) == delim:
                        break
                    lines.append(line)
                bodies.append(("\n".join(lines), quoted))
            pending = []
            continue
        out.append(c)
        i += 1
    if pending:
        raise ValueError("unterminated here-document")
    return "".join(out), bodies


def substitutions(cmd):
    """Inner text of every $(...), <(...), >(...) and backtick span, quotes ignored."""
    found = []
    i, n = 0, len(cmd)
    while i < n:
        if cmd.startswith("$((", i):
            # Arithmetic. Bash may re-parse it as a subshell, so its text is still checked as a
            # command, with the shift operators blanked so `1 << 2` is not read as a here-document.
            end = _skip_arith(cmd, i)
            found.append(cmd[i + 3:end - 2].replace("<<", "  ").replace(">>", "  "))
            i += 3
            continue
        if cmd[i] in "$<>" and i + 1 < n and cmd[i + 1] == "(":
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(cmd[j], 0)
                j += 1
            if depth:
                raise Deny("unbalanced command substitution")
            found.append(cmd[i + 2:j - 1])
            i = i + 2
            continue
        i += 1
    ticks = [m.start() for m in re.finditer(r"(?<!\\)`", cmd)]
    if len(ticks) % 2:
        raise Deny("unbalanced backtick substitution")
    found.extend(cmd[a + 1:b] for a, b in zip(ticks[::2], ticks[1::2]))
    return found


def basename(word):
    return word.rstrip("/").rsplit("/", 1)[-1]


def strip_prefix_noise(tokens):
    """Drop leading assignments and redirections (with their targets)."""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if ASSIGN_RE.match(tok):
            i += 1
        elif is_redirect(tok):
            i += 2
        elif tok.isdigit() and i + 1 < len(tokens) and is_redirect(tokens[i + 1]):
            i += 1
        else:
            break
    return tokens[i:]


def positional_args(args):
    out, skip = [], False
    for k, tok in enumerate(args):
        if skip:
            skip = False
            continue
        if is_redirect(tok):
            skip = True
            continue
        if tok.isdigit() and k + 1 < len(args) and is_redirect(args[k + 1]):
            continue
        out.append(tok)
    return out


def check_segment(tokens, depth, seen, strict=True):
    """Check one simple command. `strict` is off for candidate words found after a prefix."""
    tokens = strip_prefix_noise(tokens)
    if not tokens:
        return
    word, args = tokens[0], tokens[1:]
    name = basename(word)

    if name == "ofa" or word.endswith("/bin/ofa"):
        seen.ofa = True
        return
    if strict and word not in ("[", "[[") and DYNAMIC_RE.search(word):
        raise Deny(f"command word {word!r} is computed at run time")

    if name in PREFIXES:
        # The real command may be any later word (options and their values vary per prefix):
        # check every suffix as a command, and every multi-word argument as a command string.
        for k, tok in enumerate(args):
            check_segment(args[k:], depth + 1, seen, strict=False)
            if any(c.isspace() for c in tok):
                check_command(tok, depth + 1, seen)
        return
    if name == "find":
        for k, tok in enumerate(args):
            if tok in FIND_EXEC and k + 1 < len(args):
                check_segment(args[k + 1:], depth + 1, seen, strict=False)
        return
    if name in DB_COMMANDS:
        raise Deny(f"{name} runs against Postgres or Odoo directly; use ofa")
    if name == "docker":
        if set(args) & {"exec", "run", "cp"} and any("odoo-pg" in a for a in args):
            raise Deny("docker access to the odoo-pg container; use ofa")
    if name in SHELLS:
        pos = positional_args(args)
        c_opt = next((k for k, a in enumerate(pos) if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", a)), None)
        if c_opt is not None:
            for a in pos[c_opt + 1:]:
                if not a.startswith("-"):
                    check_command(a, depth + 1, seen)
        elif not [a for a in pos if not a.startswith("-")] or "-s" in pos:
            raise Deny(f"{name} reading commands from stdin is not inspectable")
        return
    if name == "eval":
        check_command(" ".join(args), depth + 1, seen)
        return
    if PYTHON_RE.match(name):
        seen.add("interpreter")
        for k, a in enumerate(args):
            if (a == "-m" and k + 1 < len(args) and re.match(r"^odoo(\.|$)", args[k + 1])) \
                    or re.match(r"^-modoo(\.|$)", a) or basename(a) == "odoo-bin":
                raise Deny("python invocation of the Odoo server; use ofa")
        return
    if name in INTERPRETERS:
        seen.add("interpreter")
    elif name in NETWORK:
        seen.add("network")


def check_command(cmd, depth, seen):
    if depth > MAX_DEPTH:
        raise Deny("command nesting deeper than %d" % MAX_DEPTH)
    cmd = LINE_CONTINUATION_RE.sub(r"\1", cmd)
    cmd, bodies = split_heredocs(cmd)
    # A body is data, not commands. It is expanded only when its delimiter is unquoted.
    # The rule 5 raw-string check in check_bash still sees every body.
    for text in [cmd] + [body for body, quoted in bodies if not quoted]:
        for inner in substitutions(text):
            check_command(inner, depth + 1, seen)
    tokens = tokenize(cmd)
    seen.texts.append(" ".join(tokens))  # dequoted, so "localhost:80""70" is seen as one URL
    for segment in split_segments(tokens):
        check_segment(segment, depth, seen)


class Seen(set):
    """Kinds of command words met ("network", "interpreter") plus the dequoted text of each level."""

    def __init__(self):
        super().__init__()
        self.texts = []
        self.ofa = False


def check_bash(cmd):
    seen = Seen()
    check_command(cmd, 0, seen)
    texts = [LINE_CONTINUATION_RE.sub(r"\1", cmd)] + seen.texts
    if any(MARKER_ACCESS_RE.search(t) for t in texts):
        raise Deny("command touches the guard's session markers")
    if seen and any(RAW_ODOO_RE.search(t) for t in texts):
        raise Deny("network or interpreter call to an Odoo endpoint, an Odoo port or the Postgres port")
    if "interpreter" in seen and any(RAW_INTERPRETER_RE.search(t) for t in texts):
        raise Deny("interpreter call that mentions a Postgres or Odoo client or port")


# ---------------------------------------------------------- navigation rule

def check_url(url):
    if url == "about:blank":
        return
    if any(ord(c) <= 0x20 or c == "\\" for c in url):
        raise Deny("URL contains whitespace, control characters or backslashes")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise Deny(f"scheme {parts.scheme or '(none)'!r} is not http or https")
    host = (parts.hostname or "").lower()
    if not host:
        raise Deny("URL has no host")
    if host in LOOPBACK_HOSTS:
        return
    path = parts.path or "/"
    decoded = unquote(path)
    if "/../" in decoded + "/" or "/./" in decoded + "/" or re.search(r"%(2f|5c)", path, re.I):
        raise Deny("URL path has dot segments or encoded separators")
    for allowed_host, prefix in NAV_ALLOWLIST:
        if host == allowed_host and path.startswith(prefix):
            return
    raise Deny(f"navigation to {host}{path} is not on the allowlist")


def check_script(fn):
    m = SCRIPT_DENY.search(fn)
    if m:
        raise Deny(f"in-page script uses {m.group(0)!r}; scripts may not navigate or use the network")


# ----------------------------------------------------------- session scope

def marker_path(event):
    """Path of this session's marker, or None when the event or environment cannot name one."""
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    session_id = event.get("session_id")
    if not data_dir or not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        return None
    return os.path.join(data_dir, MARKER_DIR, session_id)


def command_uses_ofa(cmd):
    seen = Seen()
    try:
        check_command(cmd, 0, seen)
    except Exception:  # a denied or unparsable line may still run ofa: fall back to the plain word
        return bool(OFA_WORD_RE.search(cmd))
    return seen.ofa


def is_activating(event):
    name = event.get("hook_event_name")
    if name == "UserPromptSubmit":
        prompt = event.get("prompt")
        return isinstance(prompt, str) and bool(ACTIVATING_PROMPT_RE.search(prompt))
    if name != "PreToolUse":
        return False
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return False
    if event.get("tool_name") == SKILL_TOOL:
        return tool_input.get("skill") in ACTIVATING_SKILLS
    cmd = tool_input.get("command")
    return event.get("tool_name") == BASH_TOOL and isinstance(cmd, str) and command_uses_ofa(cmd)


def prune_markers(directory, now):
    """Drop markers unused for MARKER_MAX_AGE_SECONDS. Never fails the activation."""
    try:
        for entry in os.scandir(directory):
            if now - entry.stat().st_mtime > MARKER_MAX_AGE_SECONDS:
                os.unlink(entry.path)
    except OSError:
        pass


def activate(marker):
    if marker is None:
        raise ValueError("no session id or plugin data directory to record the session in")
    directory = os.path.dirname(marker)
    os.makedirs(directory, exist_ok=True)
    with open(marker, "a"):
        pass
    prune_markers(directory, time.time())


def handoff_path():
    """Path of this process's /clear handoff, or None when the environment cannot name one."""
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    pid = os.environ.get("CLAUDE_PID", "")
    if not data_dir or not CLAUDE_PID_RE.match(pid):
        return None
    return os.path.join(data_dir, MARKER_DIR, f"clear.{pid}")


def carry_over_clear(event, marker, active):
    """Keep an active session active across /clear. Only ever adds a guard, never removes one."""
    path = handoff_path()
    if path is None:
        return
    if event.get("hook_event_name") == "SessionEnd":
        if active and event.get("reason") == "clear":
            with open(path, "a"):
                pass
            os.utime(path)
    elif event.get("source") == "clear" and os.path.exists(path):
        fresh = time.time() - os.stat(path).st_mtime <= CLEAR_HANDOFF_MAX_AGE_SECONDS
        os.unlink(path)
        if fresh:
            activate(marker)


# --------------------------------------------------------------------- main

def decide(event):
    """Raise Deny, or return None to allow. Only called for active sessions."""
    if not isinstance(event, dict):
        raise ValueError("event is not an object")
    if event.get("hook_event_name") == "UserPromptSubmit":
        return
    tool = event["tool_name"]
    tool_input = event["tool_input"]
    if tool == BASH_TOOL:
        cmd = tool_input["command"]
        if not isinstance(cmd, str):
            raise TypeError("command is not a string")
        check_bash(cmd)
    elif tool == SCRIPT_TOOL:
        fn = tool_input["function"]
        if not isinstance(fn, str):
            raise TypeError("function is not a string")
        check_script(fn)
    elif tool in NAV_TOOLS:
        url = tool_input["url"]
        if not isinstance(url, str):
            raise TypeError("url is not a string")
        check_url(url)
    elif tool != SKILL_TOOL:
        raise Deny(f"unexpected tool {tool!r} routed to the guard")


def session_state(stdin):
    """(event, marker, active, activating). Nothing here may raise: errors mean an inactive session."""
    try:
        event = json.loads(stdin.read())
        if not isinstance(event, dict):
            return None, None, False, False
        marker = marker_path(event)
        active = marker is not None and os.path.exists(marker)
        try:
            activating = is_activating(event)
        except Exception:
            activating = False
        return event, marker, active, activating
    except BaseException:
        return None, None, False, False


def main(stdin=None, stderr=None):
    stdin = sys.stdin if stdin is None else stdin
    stderr = sys.stderr if stderr is None else stderr
    event, marker, active, activating = session_state(stdin)
    if event is not None and event.get("hook_event_name") in SESSION_EVENTS:
        try:
            carry_over_clear(event, marker, active)
        except Exception as e:  # these events cannot block anything, so all that is left is to say it
            print(f"ofa guard: could not keep the session guarded across /clear ({type(e).__name__})", file=stderr)
        return 0
    if not active and not activating:
        return 0
    try:
        if active:
            os.utime(marker)  # the age counts from the last use, so a session in use never lapses
        else:
            activate(marker)
        decide(event)
        return 0
    except Deny as e:
        print(f"ofa guard: denied: {e}", file=stderr)
        return 2
    except BaseException as e:  # fail closed on anything, including tokenizer errors
        print(f"ofa guard: internal error, denying ({type(e).__name__})", file=stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
