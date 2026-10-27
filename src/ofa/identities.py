"""Test identities: the ofa_user_N users `ofa provision` creates, each with its own API key.

A scenario step runs `as` one of them to prove what a role can and cannot do; the bot is an
administrator and skips every approval. Roles come from plan ops that adopt these users. They can
never hold an administrator group: that is checked on the requested groups before a write and on
`all_group_ids` after it.
"""
import os
import re

from ofa import config, refs
from ofa.errors import EnvError, GuardError

LOGINS = ("ofa_user_1", "ofa_user_2", "ofa_user_3")
LOGIN_RE = re.compile(r"^ofa_user_[1-3]$")
USERS_MODEL = "res.users"
GROUPS_MODEL = "res.groups"
ADMIN_GROUPS = ("base.group_system", "base.group_erp_manager")
BASE_USER_GROUP = "base.group_user"


def key_path(db, login):
    return config.config_dir() / "keys" / f"{db}.{login}.key"


def write_key(db, login, key):
    path = key_path(db, login)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    return path


def remove_keys(db):
    for login in LOGINS:
        key_path(db, login).unlink(missing_ok=True)


def read_key(target, login):
    try:
        key = key_path(target.db, login).read_text().strip()
    except OSError:
        key = ""
    if not key:
        raise EnvError("KEY_MISSING", f"no key for test user {login} of target {target.name}; ofa reset {target.name}")
    return key


def is_test_login(login):
    return isinstance(login, str) and bool(LOGIN_RE.match(login))


def login_of(client, uid):
    rows = client.call(USERS_MODEL, "read", ids=[uid], fields=["login"])
    return rows[0]["login"] if rows else None


def _admin_group_ids(client):
    return {refs.resolve(client, {"$ref": xmlid}, {}) for xmlid in ADMIN_GROUPS}


def check_requested(client, login, group_ids):
    """Refuse, before any write, groups for a test user that are or imply an administrator group."""
    group_ids = sorted(set(group_ids))
    if not group_ids:
        return
    rows = client.call(GROUPS_MODEL, "read", ids=group_ids, fields=["all_implied_ids"])
    closure = set(group_ids).union(*(r["all_implied_ids"] for r in rows))
    if closure & _admin_group_ids(client):
        raise GuardError("ADMIN_GROUP_ON_TEST_USER",
                         f"{login} would get an administrator group ({' or '.join(ADMIN_GROUPS)}); refused")


def check_held(client, login, uid):
    """After a write: the user's effective groups hold no administrator group, else reset it and refuse."""
    effective = set(client.call(USERS_MODEL, "read", ids=[uid], fields=["all_group_ids"])[0]["all_group_ids"])
    if effective & _admin_group_ids(client):
        base = refs.resolve(client, {"$ref": BASE_USER_GROUP}, {})
        client.call(USERS_MODEL, "write", ids=[uid], vals={"group_ids": [[6, 0, [base]]]})
        raise GuardError("ADMIN_GROUP_ON_TEST_USER",
                         f"{login} ended up with an administrator group; reset to {BASE_USER_GROUP} and refused")


def set_commands(value):
    """The ids of a resolved `{"$set"}` x2many value, or None when it is anything else ($add, a bare list)."""
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], list) and len(value[0]) == 3 \
            and value[0][0] == 6:
        return list(value[0][2])
    return None


def describe(client, uid):
    """{"login", "groups": [xmlids of all_group_ids, sorted]} for the report."""
    row = client.call(USERS_MODEL, "read", ids=[uid], fields=["login", "all_group_ids"])[0]
    data = client.call("ir.model.data", "search_read",
                       domain=[["model", "=", GROUPS_MODEL], ["res_id", "in", row["all_group_ids"]]],
                       fields=["module", "name", "res_id"])
    names = {r["res_id"]: f"{r['module']}.{r['name']}" for r in data}
    return {"login": row["login"],
            "groups": sorted(names.get(g, f"{GROUPS_MODEL},{g}") for g in row["all_group_ids"])}
