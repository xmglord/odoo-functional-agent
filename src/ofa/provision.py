"""Demo database lifecycle: provision, drop, reset, template build (C13)."""
import fcntl
import os
import re
import shutil
import string
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ofa import client, config, guard, identities, pg
from ofa.errors import EnvError, GuardError, OfaError, UsageError

NAME_RE = re.compile(r"^[a-z0-9_]{1,40}$")
TEMPLATE_RE = re.compile(r"^ofa_tpl_[0-9]+$")
KEY_SENTINEL = "OFA_KEY="
USER_KEY_SENTINEL = "OFA_USER_KEY="
# Groups added to ofa_bot on top of the admin's. Spike S8 found none were needed.
EXTRA_BOT_GROUPS = ()
SHELL_TEMPLATE = Path(__file__).resolve().parent / "shell" / "provision.py.tmpl"


def db_name(name):
    if not NAME_RE.match(name or ""):
        raise UsageError(f"target name {name!r} must match {NAME_RE.pattern}")
    return f"ofa_demo_{name}"


def key_path(db):
    return config.config_dir() / "keys" / f"{db}.key"


def filestore(server, db):
    return server.data_dir / "filestore" / db


@contextmanager
def provision_lock():
    d = config.config_dir()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(d / "provision.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def odoo_cmd(server, *args, command=None):
    # odoo-bin takes its subcommand (shell, ...) before any option.
    head = [str(server.python), str(server.odoo_bin)] + ([command] if command else [])
    return head + ["-c", str(server.odoo_conf), *args]


def run_provision_shell(server, db, marker):
    script = string.Template(SHELL_TEMPLATE.read_text()).substitute(
        marker=marker, extra_groups=repr(list(EXTRA_BOT_GROUPS)), test_logins=repr(list(identities.LOGINS)))
    try:
        out = subprocess.run(odoo_cmd(server, "-d", db, "--no-http", "--log-level=warn", command="shell"),
                             input=script, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise EnvError("SHELL_TIMEOUT", f"odoo-bin shell timed out on {db}") from None
    lines = out.stdout.splitlines()
    keys = [line[len(KEY_SENTINEL):].strip() for line in lines if line.startswith(KEY_SENTINEL)]
    user_keys = dict(line[len(USER_KEY_SENTINEL):].strip().split("=", 1) for line in lines
                     if line.startswith(USER_KEY_SENTINEL) and "=" in line[len(USER_KEY_SENTINEL):])
    if out.returncode != 0 or len(keys) != 1 or not keys[0]:
        # Never echo the shell output: on a partial failure it may hold the key.
        raise EnvError("SHELL_FAILED", f"odoo-bin shell on {db} exited {out.returncode} without one {KEY_SENTINEL} line")
    if sorted(user_keys) != sorted(identities.LOGINS) or not all(user_keys.values()):
        raise EnvError("SHELL_FAILED", f"odoo-bin shell on {db} did not print a key for every test user")
    return keys[0], user_keys


def _write_key(db, key):
    path = key_path(db)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    return path


def _remove_local(server, db, name=None):
    shutil.rmtree(filestore(server, db), ignore_errors=True)
    key_path(db).unlink(missing_ok=True)
    identities.remove_keys(db)
    if name is not None:
        try:
            config.remove_target(name)
        except GuardError:
            pass


def provision(name, log=print):
    db = db_name(name)
    cfg = config.load()
    server = cfg.server
    if name in cfg.targets:
        raise UsageError(f"target {name} is already registered; use ofa reset {name}")
    with provision_lock():
        if pg.db_exists(server, db):
            raise UsageError(f"database {db} already exists")
        marker = str(uuid.uuid4())
        registered = False
        try:
            pg.create_from_template(server, db, server.template_db)
            src = filestore(server, server.template_db)
            if src.is_dir():
                shutil.copytree(src, filestore(server, db), symlinks=True)
            key, user_keys = run_provision_shell(server, db, marker)
            key_file = _write_key(db, key)
            for login, user_key in user_keys.items():
                identities.write_key(db, login, user_key)
            config.add_target(config.Target(
                name=name, db=db, url=server.url, marker=marker, api_key_file=str(key_file),
                created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                odoo_version=server.odoo_version, edition=server.edition))
            registered = True
            client.open_client(name)
        except BaseException:
            # Roll back only what this call created: the name was free and the DB absent.
            pg.drop_db(server, db)
            _remove_local(server, db, name if registered else None)
            raise
    log(f"provisioned {name} ({db})")
    return 0


def drop_one(cfg, name):
    target = cfg.target(name)
    guard.check_static(target)
    server = cfg.server
    if not pg.db_exists(server, target.db):
        _remove_local(server, target.db, name)
        return f"dropped {name}: database {target.db} was already gone, local state removed"
    try:
        marker = pg.read_marker(server, target.db)
    except EnvError:
        marker = None
    if marker is None:
        raise GuardError("MARKER_MISSING", f"{target.db} has no ofa.demo_marker; refusing to drop it")
    if marker != target.marker:
        raise GuardError("MARKER_MISMATCH", f"{target.db} marker does not match the registered one; refusing to drop it")
    pg.drop_db(server, target.db)
    _remove_local(server, target.db, name)
    return f"dropped {name} ({target.db})"


def drop(names, log=print):
    code = 0
    for name in names:
        try:
            log(drop_one(config.load(), name))
        except OfaError as e:
            print(f"ofa: {e.label}: {e.msg}", file=sys.stderr)
            code = max(code, e.exit_code)
    return code


def reset(name, log=print):
    db_name(name)
    code = drop([name], log)
    if code:
        return code
    return provision(name, log)


def template_build(name=None, log=print):
    cfg = config.load()
    server = cfg.server
    name = name or server.template_db
    if name != server.template_db or not TEMPLATE_RE.match(name):
        raise GuardError("BAD_NAME", f"template must be server.template_db and match {TEMPLATE_RE.pattern}")
    pg.drop_db(server, name)
    shutil.rmtree(filestore(server, name), ignore_errors=True)
    modules = ",".join(server.template_modules)
    log(f"building {name} with {modules} (several minutes)")
    out = subprocess.run(odoo_cmd(server, "-d", name, "-i", modules, "--with-demo", "--stop-after-init"),
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise EnvError("TEMPLATE_FAILED", f"odoo-bin exited {out.returncode} building {name}")
    log(f"built {name}")
    return 0
