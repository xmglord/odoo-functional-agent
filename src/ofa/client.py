"""JSON-2 client for demo targets (C3). Every client is built by open_client."""
import json
import socket
import time
import urllib.error
import urllib.request

from ofa import config, guard, identities
from ofa.errors import EnvError, GuardError, OdooError, UsageError

TIMEOUT = 120
MARKER_KEY = "ofa.demo_marker"
# After a DB is dropped and re-created under the same name, the shared server's
# pool still holds connections to the old one; each request that borrows one
# fails once (HTML 404) and the dead connection is discarded.
STALE_POOL_RETRIES = 5

# Methods that take no `ids` (@api.model). Every other method is a record method
# and must get a non-empty `ids`, because the server silently does nothing on an
# empty recordset. Callers of another @api.model method pass api_model=True.
MODEL_METHODS = frozenset({
    "create", "search", "search_read", "search_count", "fields_get", "default_get",
    "name_search", "name_create", "check_access_rights", "context_get",
    "get_str", "set_str", "get_bool", "set_bool", "get_int", "set_int", "get_float", "set_float",
})

_OPEN = object()


class OdooClient:
    def __init__(self, target, key, xmlid_store, _token=None):
        if _token is not _OPEN:
            raise UsageError("OdooClient is built only by client.open_client")
        self.target = target
        self.xmlid_store = xmlid_store
        self._key = key
        self.call_log = []
        self._bot_uid = None

    def __repr__(self):
        return f"OdooClient({self.target.name})"

    def call(self, model, method, *, ids=None, context=None, api_model=False, **params):
        is_model_method = api_model or method in MODEL_METHODS
        if is_model_method and ids:
            raise UsageError(f"{model}/{method} takes no ids")
        if not is_model_method and not ids:
            raise UsageError(f"{model}/{method} is a record method and needs non-empty ids")
        body = dict(params)
        if ids is not None:
            body["ids"] = list(ids)
        if context is not None:
            body["context"] = context
        url = f"{self.target.url.rstrip('/')}/json/2/{model}/{method}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"bearer {self._key}",
            "X-Odoo-Database": self.target.db,
            "Content-Type": "application/json",
        })
        start = time.monotonic()
        status = None
        try:
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    status = resp.status
                    return json.loads(resp.read() or b"null")
            except urllib.error.HTTPError as e:
                status = e.code
                raise _map_http_error(e, self.target) from None
            except (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout):
                status = "SERVER_DOWN"
                raise EnvError("SERVER_DOWN", f"{self.target.url} not answering; run ofa server start") from None
        finally:
            self.call_log.append({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model": model, "method": method, "ids": list(ids) if ids is not None else None,
                "duration_ms": round((time.monotonic() - start) * 1000), "status": status,
            })

    def bot_uid(self):
        if self._bot_uid is None:
            found = self.call("res.users", "search", domain=[["login", "=", "ofa_bot"]], limit=1)
            if not found:
                raise EnvError("BOT_MISSING", f"no ofa_bot user in {self.target.db}")
            self._bot_uid = found[0]
        return self._bot_uid


def _map_http_error(e, target):
    try:
        text = e.read().decode("utf-8", errors="replace")
    finally:
        e.close()
    try:
        body = json.loads(text)
    except ValueError:
        body = None
    if not isinstance(body, dict):
        if e.code == 404:
            return EnvError("DB_NOT_SERVED",
                            f"database {target.db} is not served at {target.url}: it does not exist or dbfilter rejects it")
        return OdooError(e.code, "", text[:500])
    # Only name and message survive: debug (a server traceback), arguments and
    # context are dropped here and never stored.
    return OdooError(e.code, str(body.get("name") or ""), str(body.get("message") or ""))


def open_client(target_name, *, cfg=None, required_edition=None):
    cfg = cfg or config.load()
    target = cfg.target(target_name)
    guard.check_static(target, required_edition)
    client = OdooClient(target, target.api_key(), cfg.server.xmlid_store, _OPEN)
    for attempt in range(STALE_POOL_RETRIES + 1):
        try:
            marker = client.call("ir.config_parameter", "get_str", key=MARKER_KEY)
            break
        except EnvError as e:
            if e.code != "DB_NOT_SERVED" or attempt == STALE_POOL_RETRIES:
                raise
        except OdooError as e:
            # The registered key does not work on this DB, so its marker cannot be
            # checked: that is a guard refusal, not an environment problem.
            if e.status in (401, 403):
                raise GuardError("MARKER_UNVERIFIABLE", f"{target.db}: the registered key cannot read the marker") from None
            raise
    # get_str returns "" for a missing key.
    if marker in ("", None):
        raise GuardError("MARKER_MISSING", f"{target.db} has no {MARKER_KEY}")
    if marker != target.marker:
        raise GuardError("MARKER_MISMATCH", f"{target.db} marker does not match the registered one")
    return client


def open_identity(bot, login):
    """A client that acts as the test user `login` on the bot's target, already guarded by open_client.

    Test users cannot read the demo marker (system parameters are admin-only), so the guard is the bot's.
    Calls go to the bot's call log, so calls.jsonl keeps one ordered record of the run.
    """
    if not identities.is_test_login(login):
        raise GuardError("NOT_A_TEST_USER", f"{login!r} is not a test user (ofa_user_1..3)")
    user = OdooClient(bot.target, identities.read_key(bot.target, login), bot.xmlid_store, _OPEN)
    user.call_log = bot.call_log
    return user
