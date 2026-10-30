# Demo-only guard

The agent must refuse, or be unable, to act on any Odoo database that is not a demo database it created. The
machine it runs on may also host non-demo databases on the same Postgres server, so the guard has two layers plus
a hardened server config. No single layer is trusted alone.

## Layer a: the `ofa` client

Every `ofa` command that talks to Odoo builds its client through one constructor, `open_client`, so no subcommand
can skip these checks:

- the target is listed in the `[targets.*]` tables of the machine-local config `~/.config/ofa/config.toml` (not in the repo)
- its database name matches `^ofa_demo_[a-z0-9_]{1,40}$`
- its URL host is loopback (`127.0.0.1`, `localhost` or `::1`)
- the database's `ir.config_parameter` key `ofa.demo_marker` equals the UUID that `ofa provision` recorded. It is
  checked on every client construction, for reads as well as writes. Reading a config parameter over JSON-2
  (`ir.config_parameter/get_str`) needs the `base.group_system` group. The `ofa_bot` user has it because
  provisioning copies the admin user's `group_ids` to it; this was confirmed live (`has_group('base.group_system')`
  is true for the bot). `ofa apply` later adds any group the admin gained from a newly installed module, and never
  more than the admin has (see `docs/plan_format.md`). A missing marker reads back as an empty string, not null; the client treats both as
  `MARKER_MISSING`. When the registered key is rejected while reading the marker (401/403), the marker cannot be
  verified and the client refuses with `MARKER_UNVERIFIABLE` (exit 3), not as an environment error.

Only `provision` writes markers and creates API keys, and API keys exist only for demo databases. `drop` and
`reset` act only on names that pass the same checks. A database `ofa` did not create fails the marker check even
if someone adds it to the registry by hand; a production-named database fails the name check.

Layer a covers everything `ofa` does. It cannot stop a shell command that bypasses `ofa` (raw `psql`, `curl` to
the JSON-2 API). That is layer b's job.

## Layer b: the PreToolUse hook

The plugin ships `hooks/hooks.json`, which runs `hooks/ofa_guard.sh` (a small wrapper around
`hooks/ofa_guard_hook.py`) before every `Bash` call and every `mcp__firefox-devtools__navigate_page` /
`mcp__firefox-devtools__new_page` / `mcp__firefox-devtools__evaluate_script` call, plus on `Skill` calls and
`UserPromptSubmit`. In an active session the hook reads the event JSON on stdin (`tool_name`, and
`tool_input.command`, `tool_input.url` or `tool_input.function`) and either exits 0 with no output (allow) or exits 2
with one line on stderr (deny); Claude Code shows that line to the model.

### When it acts

An installed plugin's hooks run in every Claude Code session on the machine, whatever the project. So **the hook
acts only from the moment a session uses the agent; before that it allows everything and there is no protection.**
Other projects keep working: `psql`, `odoo-bin` and any browser navigation pass in a session that never touched the
agent.

A session becomes active, and stays active, on the first of these:

- a `Skill` call for `odoo-functional-agent:odoo-functional` or `odoo-functional-agent:odoo-explain`
- a Bash command that has `ofa` (or a path ending in `/bin/ofa`) in a command position
- a prompt with a `Target: <name>` line, or a prompt that starts with `/odoo-functional-agent:odoo-functional` or
  `/odoo-functional-agent:odoo-explain` (a skill typed by the user makes no `Skill` call)

Activation writes an empty marker at `${CLAUDE_PLUGIN_DATA}/active_sessions/<session_id>`. It outlives the session, so a
resumed session stays guarded, and each use refreshes it. Each activation prunes markers unused for 30 days, Claude
Code's default transcript retention (`cleanupPeriodDays`): past that, a session cannot be resumed anyway. The activating
call is itself checked, so `ofa status; psql -l` is denied. Subagents are covered: a subagent's hook event carries the
parent's `session_id` (measured with Claude Code 2.1.312). This is why the hook is not declared in the skills'
frontmatter: Claude Code supports that, but such a hook does not run inside subagents (same measurement).

What can leave an agent session without the guard:

- **By accident.** The model works without invoking a skill, running `ofa` or seeing a `Target:` line. A raw `psql` in
  that session is not checked, and layer a does not cover it.
- **`/clear`: not measured.** It may start a new `session_id`. If it does, the session is inactive again until the
  next activating event.
- **`--resume` after 30 days.** A session resumed within 30 days of its last use stays active: measured with `claude -p --resume`, 2.1.312,
  one run, the same `session_id` kept its marker and the raw `psql` was denied. With
  `cleanupPeriodDays` raised above 30, a session idle for longer has lost its marker and is inactive until the next
  activating event. An interactive `--resume` was not measured, and `--fork-session` gets a new `session_id`, so it
  starts inactive. Compaction keeps the session running and is not expected to change this, also not measured.
- **On purpose.** `disableAllHooks` or `--settings '{"disableAllHooks": true}'`. Deleting the marker is denied for
  Bash commands that mention `active_sessions`, `plugins/data` or `CLAUDE_PLUGIN_DATA`, but a script file that deletes
  it is not inspected (see [Known gaps](#known-gaps)).

### Failure handling

- A hook failure must not block sessions that never used the agent, so the order is fixed: first decide whether the
  session is active or the event activates it. **With no marker and no activating event the hook exits 0, even on
  invalid JSON or a missing `session_id`.**
- In an active session, or on an activating event, any error denies: a missing `tool_input`, `command` or `url`, a
  tokenizer error (for example an unbalanced quote), a marker that cannot be written, or any unexpected exception exits
  2 with `ofa guard: internal error, denying (<exception class>)`.
- Every handler has `"timeout": 10` and `"onFailure": "block"`. Without `onFailure`, Claude Code lets the tool
  call through when a hook crashes (exit 1) or times out; with it, both block. This was verified against Claude
  Code 2.1.310. That setting cannot tell sessions apart, so the failures Python cannot report are sorted out before
  they reach Claude Code: `ofa_guard.sh` runs Python under an 8 second limit, and on any result other than 0 or 2
  (Python missing, crashed, hung) it denies only if the session's marker exists or the event looks activating, and
  otherwise exits 0. The command in `hooks.json` does the same marker check if the wrapper itself is gone.
- What remains: if `sh` cannot start, `onFailure` blocks the call in every session. Claude Code's Bash tool needs a
  shell too, so that machine is already broken.
- With Python broken, the wrapper's activation check is coarser than Python's: it denies any event with the word `ofa`
  or the plugin's skill prefix, and prompts with a `Target:` text anywhere.

### Bash rules

1. **Tokenizing.** `shlex` in POSIX mode with punctuation characters `( ) ; < > | &` and newline. Comments are
   not stripped: `#` inside a word is literal, as in bash (`true#; psql` is two commands). Quoted text never splits
   a command, so `echo "a;psql"` is one `echo`. Backslash-newline continuations are joined first.
2. **Here-documents.** `<<WORD`, `<<'WORD'`, `<<"WORD"` and `<<-WORD` bodies are data, not commands: they are
   removed before command parsing, so a commit message passed with `git commit -F - <<'EOF'` can mention any
   word. Substitutions in a body with an unquoted delimiter are still checked, the network/interpreter check
   (rule 8) still reads every body, and an unterminated body is denied. `<<<` here-strings are ordinary arguments.
3. **Command positions.** A new command starts after any token made only of `;`, `&`, `|`, newline, `(` or `)`
   (so `&&`, `||`, `|&`, `;;`, `)&&` all count), and after the standalone words `{ } ! if then else elif do while
   until`. Redirections (`>`, `2>`, `<<`, `>&`, ...) and their targets, and leading `VAR=value` assignments, are
   skipped before the command word.
4. **Substitutions.** The text inside every `$(...)`, `<(...)`, `>(...)` and backtick pair, including inside double
   quotes, is checked recursively with the same rules. An unbalanced one is denied.
5. **Shell re-entry.** `bash`, `sh`, `zsh`, `dash`, `ksh` (and a few more) with a `-c`-style option have their
   command argument checked recursively; `eval` has its joined arguments checked. A shell with no `-c` and no
   script argument (reading commands from stdin or a here-document) is denied. Nesting deeper than 5 levels is
   denied.
6. **Command word.** Denied when its basename is `psql`, `pg_dump`, `pg_dumpall`, `pg_restore`, `dropdb`,
   `createdb`, `odoo-bin`, `odoo` or another Postgres client tool; when it is `docker` with `exec`, `run` or `cp`
   and an `odoo-pg` argument; or when it is `python*` with `-m odoo` or an `odoo-bin` argument. A command word
   that is computed at run time (`$X`, `$(...)`, globs such as `ps?l`, brace expansions) is denied, because its
   value cannot be known.
7. **Prefixes.** After `sudo`, `env`, `nohup`, `time`, `exec`, `command`, `xargs`, `timeout`, `nice`, `watch`,
   `ssh` and similar runners, every later word is treated as a possible command word, and every multi-word
   argument is checked as a command string. `find ... -exec` is handled the same way.
8. **Network and interpreters.** When any command word is a network client (`curl`, `wget`, `http`, `nc`, ...) or
   an interpreter (`python*`, `node`, `perl`, `ruby`, `php`, `awk`, ...), the raw command and its dequoted form are
   checked. They are denied when they contain `/json/2/`, `/jsonrpc`, `/xmlrpc`, `/web/`, or any host followed by
   a port in `8060-8099` or `5432`. The port check deliberately ignores the host: loopback has too many spellings
   (`127.1`, `0`, `[::ffff:127.0.0.1]`) to enumerate. For interpreters only, the command is also denied when it
   mentions `psql`, `pg_dump`, `pg_restore`, `createdb`, `dropdb`, `odoo-bin`, `psycopg`, `asyncpg`, `pg8000`,
   `import odoo` / `from odoo`, or a bare `80xx` / `5432` number.
9. **`ofa` is allowed.** A command word `ofa`, or a path ending in `/bin/ofa`, is allowed; the other commands in
   the same line are still checked.
10. **Session markers.** A command that mentions `active_sessions`, `plugins/data` or `CLAUDE_PLUGIN_DATA` is denied,
    in any position, so a session cannot switch its own guard off from the command line.

Words are matched in command position only, so `grep -rn psql src/` and `git commit -m "mention psql"` are
allowed and the repo stays developable with the plugin enabled.

### Navigation rule (deny by default)

For `navigate_page` and `new_page` (both carry the target in `tool_input.url`):

- `about:blank` is allowed.
- URLs with whitespace, control characters or backslashes are denied (browsers and Python parse those
  differently).
- A scheme other than `http` / `https` is denied (`file:`, `javascript:`, `data:`, ...).
- Host `127.0.0.1`, `localhost` or `[::1]` is allowed: that is the demo server, and layer a plus `dbfilter`
  bound what it serves.
- Any other host is allowed only if `(host, path prefix)` is on `NAV_ALLOWLIST`. Paths with `.`/`..` segments or
  encoded `/` or `\` are denied before the prefix check.

`NAV_ALLOWLIST`, a constant at the top of `hooks/ofa_guard_hook.py`:

| Host | Path prefix | Why |
|---|---|---|
| `www.odoo.com` | `/documentation/` | official functional documentation |
| `github.com` | `/odoo/` | Community source, to cite code paths |

Everything else is denied, including hosted Odoo instances (`https://<name>.odoo.com/odoo/...`) and
`https://www.odoo.com/odoo/...`, which is a live Odoo database.

**Extending it.** Add a `(host, path_prefix)` tuple to `NAV_ALLOWLIST`. The host is compared exactly (lowercase,
no port, no wildcards) and the prefix with `str.startswith`, so end the prefix with `/`. Never add a host that
serves an Odoo database. Add an allow case and a neighbouring deny case to `tests/hook/test_ofa_guard_hook.py`.

### In-page script rule

`evaluate_script` runs JavaScript in the page, which can navigate anywhere without `navigate_page`. Its
`tool_input.function` is denied when it mentions a navigation or network API (`location`, `href`, `open(`,
`fetch(`, `XMLHttpRequest`, `sendBeacon`, `WebSocket`, `EventSource`, `import(`, `history`, `submit(`, `.click(`,
`document.write`, `src =`), computed access to a global (`window[...]`, `globalThis[...]`, `document[...]` and
similar), dynamic code (`eval(`, `Function(`, string `setTimeout`) or a `\u` / `\x` escape. The scripts ofa uses
(render probes, reading field values) need none of these.

## Server hardening

The local Odoo server that serves demo databases runs with:

```ini
dbfilter = ^ofa_demo_.*$
max_cron_threads = 0
list_db = False
proxy_mode = False
```

- `dbfilter` makes the HTTP layer refuse any database that is not a demo database, even on loopback.
- **`dbfilter` does not apply to cron.** Odoo's cron threads pick their databases from the full database list
  (`cron_database_list` in `odoo/service/server.py`: `db_name` if set, else `list_dbs`), not through
  `dbfilter`. `list_dbs` (`odoo/modules/db.py`) returns every database owned by the Postgres role the server
  connects as, so a demo server with cron threads that shares that role with other Odoo databases runs their
  scheduled actions too. `max_cron_threads = 0` is the control: the demo server runs no cron at all.
- `list_db = False` hides the database manager and the database list.
- `proxy_mode = False` keeps the server from trusting forwarded host headers.

`config/odoo20.conf.example` carries these settings.

## The permission mode is not a layer

Claude Code's permission settings (`--allowedTools`, the permission mode, allow and deny rules) decide which tool
calls run without asking the user. The guard does not rely on them: the hook runs on every matched tool call in
every mode, and layer a, the marker and the server hardening hold whatever the session approves.

Measured from the T26 example session's transcript on 2026-10-28 (the transcript is not kept): it ran in the `auto`
permission mode, and 89 of its 91 shell commands were not a plain `ofa` command (`cd ... && ofa ...`, `grep`, `sed`,
`python3` on the Odoo source, a `sleep`), so an allow rule like `Bash(ofa *)` matched almost none of them; the mode
approved them without a prompt, while the hook still checked each one and refused an in-page `.click()`. Each example
README states the permission mode its session ran in, when its transcript was still available to measure it.

## Known gaps

The hook is pattern matching. It narrows what a careless or adversarial command can do; it does not make that
impossible. Layer a, the marker and the server hardening are the backstop for everything that goes through Odoo's
HTTP API. Known gaps:

- **In-page navigation.** In-page clicks (`click_by_uid` on a link, or on a button whose handler navigates) can
  reach a non-loopback host without `navigate_page`; the hook does not inspect click tools, because it cannot know
  where a click leads. `evaluate_script` is covered by the in-page script rule, but that rule is a deny list: a
  script that reaches navigation through a spelling it does not list is not caught.
- **Script files.** A script written to disk and then run (`python3 x.py`, `bash x.sh`, `source x.sh`) is not
  inspected; only the command line is. Odoo's HTTP API stays closed to non-demo databases even then: the server's
  `dbfilter` answers 404 for any other database, also with a valid demo API key (measured). A script that talks to
  Postgres directly (`psql` in a subprocess, a Postgres driver) is not caught: the demo server shares its Postgres
  role with the machine's other databases, so only the hook stands between such a script and them. A here-document written to a file and then executed
  (`cat > x.sh <<'EOF'` followed by `bash x.sh`) is this same gap.
- **Indirect execution not modelled.** Tools that run a command from configuration or an argument the hook does
  not recognise as a command: `git -c core.pager=...`, git aliases, `make` targets, `npm run` scripts, editor
  invocations, functions or aliases defined in an earlier Bash call and called by a neutral name.
- **Unusual network clients.** Network access from a binary not on the network/interpreter list (for example a
  compiled program, or `openssl s_client`), or to an Odoo port outside `8060-8099`, is not caught by rule 7.
- **Remote Odoo UI paths.** `curl https://<host>/odoo/...` on the default port is not denied (no API path, no
  Odoo port). It returns HTML only; the APIs that read or write data are under the denied paths.
- **Over-denial.** The rules err towards denying. Known false positives: a quoted argument made only of separator
  characters (`echo ";" psql`), any word after a runner prefix (`xargs grep psql`, `timeout 5 grep psql`),
  interpreter commands that mention a denied word or port in any
  form, and any host on ports `8060-8099`. Run those through a script file or rephrase them.
- **Hook not loaded or not active.** The hook protects only sessions where the plugin is enabled, and only after the
  session activates it (see [When it acts](#when-it-acts)). In any other session (for example the development session
  that runs acceptance checks with raw `psql`), only layer a and the server hardening apply.
