"""Layer a of the demo-only guard: static target checks (C3, ADR-0003).

The marker check needs a live call, so it lives in client.open_client.
"""
import re
from urllib.parse import urlsplit

from ofa.errors import GuardError

DB_RE = re.compile(r"^ofa_demo_[a-z0-9_]{1,40}$")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def check_static(target, required_edition=None):
    if target is None:
        raise GuardError("NOT_REGISTERED", "no target given")
    if not DB_RE.match(target.db):
        raise GuardError("BAD_NAME", f"db {target.db} does not match {DB_RE.pattern}")
    try:
        host = urlsplit(target.url).hostname
    except ValueError:
        host = None
    if host not in LOOPBACK_HOSTS:
        raise GuardError("NOT_LOOPBACK", f"target {target.name} url host is not loopback")
    if required_edition and target.edition != required_edition:
        raise GuardError("EDITION_MISMATCH", f"target {target.name} is {target.edition}, {required_edition} required")
