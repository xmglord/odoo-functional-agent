# Demo-only guard

The agent must refuse, or be unable, to act on any Odoo database that is not a demo database it created. The
machine it runs on may also host non-demo databases on the same Postgres server, so the guard has two layers plus
a hardened server config. No single layer is trusted alone.

## Layer a: the `ofa` client

Every `ofa` command that talks to Odoo builds its client through one constructor, `open_client`, so no subcommand
can skip these checks:

- the target is listed in the machine-local registry `~/.config/ofa/targets.toml` (not in the repo)
- its database name matches `^ofa_demo_[a-z0-9_]{1,40}$`
- its URL host is loopback (`127.0.0.1`, `localhost` or `::1`)
- the database's `ir.config_parameter` key `ofa.demo_marker` equals the UUID that `ofa provision` recorded. It is
  checked on every client construction, for reads as well as writes. Reading a config parameter over JSON-2
  (`ir.config_parameter/get_str`) needs the `base.group_system` group. The `ofa_bot` user has it because
  provisioning copies the admin user's `group_ids` to it; this was confirmed live (`has_group('base.group_system')`
  is true for the bot). A missing marker reads back as an empty string, not null; the client treats both as
  `MARKER_MISSING`.

Only `provision` writes markers and creates API keys, and API keys exist only for demo databases. `drop` and
`reset` act only on names that pass the same checks. A database `ofa` did not create fails the marker check even
if someone adds it to the registry by hand; a production-named database fails the name check.

Layer a covers everything `ofa` does. It cannot stop a shell command that bypasses `ofa` (raw `psql`, `curl` to
the JSON-2 API). That is layer b's job.

## Layer b: the PreToolUse hook

The plugin ships `hooks/hooks.json`, which runs `hooks/ofa_guard_hook.py` before every `Bash` call and every
`mcp__firefox-devtools__navigate_page` / `mcp__firefox-devtools__new_page` call. The hook reads the event JSON on
stdin (`tool_name`, `tool_input.command` or `tool_input.url`) and either exits 0 with no output (allow) or exits 2
with one line on stderr (deny); Claude Code shows that line to the model.

### Failure handling

- Every handler has `"timeout": 10` and `"onFailure": "block"`. Without `onFailure`, Claude Code lets the tool
  call through when a hook crashes (exit 1) or times out; with it, both block. This was verified against Claude
  Code 2.1.310.
- Inside the script, `main()` is a catch-all: malformed JSON, a missing `tool_input`, `command` or `url`, a
  tokenizer error (for example an unbalanced quote) or any unexpected exception exits 2 with
  `ofa guard: internal error, denying (<exception class>)`. This is the in-script control; `onFailure: "block"`
  covers what the script cannot catch itself (interpreter crash, timeout).
- The hook only runs for its matched tools, so failing closed blocks only `Bash` and the two navigation tools.

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

## Known gaps

The hook is pattern matching. It narrows what a careless or adversarial command can do; it does not make that
impossible. Layer a, the marker and the server hardening are the backstop for everything that goes through Odoo's
HTTP API. Known gaps:

- **In-page navigation.** `mcp__firefox-devtools__evaluate_script` (for example `location.href = ...`) and
  in-page clicks (`click_by_uid` on a link) can navigate to a non-loopback host without `navigate_page`. The hook
  does not inspect those tools.
- **Script files.** A script written to disk and then run (`python3 x.py`, `bash x.sh`, `source x.sh`) is not
  inspected; only the command line is. Layer a still holds for anything that goes through Odoo's API, but a script
  that runs `psql` directly is not caught. A here-document written to a file and then executed
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
- **Hook not loaded.** The hook protects only sessions where the plugin is enabled. In a session without it (for
  example the development session that runs acceptance checks with raw `psql`), only layer a and the server
  hardening apply.
