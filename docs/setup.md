# Setup

What you need on your machine before the skill can configure a demo database. Everything stays local: `ofa` only
talks to an Odoo server on loopback, and only to databases it created.

## 1. Odoo 20 and PostgreSQL

- An Odoo 20.0 source checkout and a Python environment with its requirements installed. For the Enterprise
  features (the examples, the Mexican localization) also the Enterprise addons, on your own licence; keep them out
  of this repository.
- A PostgreSQL server and a role Odoo can use. Put its password in `~/.pgpass`, not in any config file.

## 2. A hardened Odoo config

Copy [config/odoo20.conf.example](../config/odoo20.conf.example) next to your checkout, as `odoo20.conf`, and fill
in the paths, the database host, port and role. Keep its hardening lines:

```ini
list_db = False
dbfilter = ^ofa_demo_.*$
max_cron_threads = 0
proxy_mode = False
```

`dbfilter` makes the server refuse any database that is not a demo one. It does not apply to cron, so
`max_cron_threads = 0` keeps scheduled jobs off every database (demo scenarios cannot rely on cron for that reason).
`ofa doctor` and `ofa server start` refuse a config without the first three.

## 3. The `ofa` config

Copy [config/ofa_config.toml.example](../config/ofa_config.toml.example) to `~/.config/ofa/config.toml` (directory
mode `0700`), or to `$OFA_CONFIG_DIR/config.toml`, and fill in the `[server]` section: the paths to `odoo-bin`, its
Python and `odoo20.conf`, the URL (`http://127.0.0.1:<port>`), the edition (`enterprise` or `community`) and the
template's module list (the example file also shows the Community one). Do not add targets by hand:
`ofa provision` writes them.

`ofa` is `bin/ofa` in this repository; with the plugin enabled it is on Claude Code's shell `PATH`. Check the
setup with:

```
ofa doctor
```

At this point `template database` and `server port answers` still say `FAIL`; the next two steps fix them.

## 4. The template database

```
ofa template build
```

builds `ofa_tpl_20` (the name comes from the config) with demo data and the configured modules. It takes several
minutes and is rebuilt only when your Odoo checkout changes. Every demo database is a copy of it, so what it
installs is what every test starts from.

## 5. The server and a demo database

```
ofa server start
ofa provision demo1
```

`ofa server start` runs Odoo with your hardened config and is idempotent. `ofa provision demo1` creates
`ofa_demo_demo1` from the template, writes its marker, and creates the `ofa_bot` user and three test users
(`ofa_user_1` to `ofa_user_3`) with their API keys in `~/.config/ofa/keys/` (files `0600`). `ofa drop demo1`
removes the database, its filestore and its keys; `ofa reset demo1` drops and provisions it again.

## 6. Claude Code

Install the plugin (see the [README](../README.md#install-as-a-plugin)) or point Claude Code at a checkout with
`--plugin-dir`. The skill provisions its own demo database when you name a target that does not exist.

Screenshots need the Firefox DevTools MCP server connected to a Firefox profile started with Marionette and a
remote debugging port, with its window visible on screen. Without it the skill keeps the read-back records as the
evidence.
