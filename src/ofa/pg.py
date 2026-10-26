"""Postgres access for provisioning, through psql as the role named in the Odoo conf.

Every database name reaching this module has already been validated against a
strict pattern by the caller; quoting is a second line of defence, not the first.
"""
import re
import subprocess
import time

from ofa.errors import EnvError, UsageError

SAFE_NAME = re.compile(r"^[a-z0-9_]{1,63}$")
BUSY = "is being accessed by other users"


def _ident(name):
    if not SAFE_NAME.match(name):
        raise UsageError(f"refusing unsafe database name {name!r}")
    return f'"{name}"'


def psql(server, sql, db="postgres"):
    cmd = ["psql", "-h", server.db_host, "-p", str(server.db_port), "-U", server.db_user, "-d", db,
           "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        raise EnvError("PSQL_MISSING", "psql is not installed") from None
    except subprocess.TimeoutExpired:
        raise EnvError("PG_TIMEOUT", f"psql timed out on {db}") from None
    if out.returncode != 0:
        raise EnvError("PG_ERROR", out.stderr.strip().splitlines()[-1] if out.stderr.strip() else f"psql exit {out.returncode}")
    return out.stdout.strip()


def db_exists(server, db):
    _ident(db)
    return psql(server, f"SELECT 1 FROM pg_database WHERE datname = '{db}'") == "1"


def create_from_template(server, db, template, retries=3, wait=3):
    sql = f"CREATE DATABASE {_ident(db)} TEMPLATE {_ident(template)}"
    for attempt in range(retries + 1):
        try:
            return psql(server, sql)
        except EnvError as e:
            if BUSY not in e.msg or attempt == retries:
                raise
            time.sleep(wait)


def drop_db(server, db):
    # WITH (FORCE) ends the shared server's pooled connections first, as Odoo's
    # own drop does; a plain DROP fails while the server holds the DB open.
    psql(server, f"DROP DATABASE IF EXISTS {_ident(db)} WITH (FORCE)")


def read_marker(server, db):
    """The ofa.demo_marker value, or None when the DB has none."""
    _ident(db)
    value = psql(server, "SELECT value FROM ir_config_parameter WHERE key = 'ofa.demo_marker'", db=db)
    return value or None
