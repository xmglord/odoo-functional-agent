"""Scenario format `ofa.scenario/1`: validation and the step runner (C8).

`load(path)` parses and validates a scenario file without touching Odoo.
`run(client, scenario)` runs one validated scenario and returns its C9 result.
"""
import json
import re
from pathlib import Path

from ofa import client as clientmod, identities, refs, wizards
from ofa.errors import EnvError, GuardError, OdooError, OfaError, ValidationError

FORMAT = "ofa.scenario/1"
AREAS = ("sales_crm", "purchase_inventory", "accounting", "multi_company", "l10n_mx")
EDITIONS = ("community", "enterprise")
ID_RE = re.compile(r"^[a-z0-9_]{1,80}$")
VAR_RE = re.compile(r"^[a-z_][a-z0-9_]{0,60}$")
OPS = ("eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "contains")

TOP_REQUIRED = ("format", "id", "area", "odoo_version", "edition", "description", "steps")
TOP_OPTIONAL = ("requires", "preconditions", "evidence", "company", "as", "users")
STEP_COMMON = ("id", "action", "model")
# Any step may name a company and a user; its calls then run in that company, as that user (each overrides the
# scenario-level `company` / `as`).
STEP_OPTIONAL = ("company", "as")
# action -> (required keys besides id/action/model, optional keys)
ACTIONS = {
    "create": (("values",), ("save_as",)),
    "write": (("target", "values"), ()),
    "call": (("target", "method"), ("params", "wizards")),
    "search": (("domain",), ("limit", "save_as", "expect")),
    "read": (("target", "fields"), ("save_as", "expect")),
    "assert": (("target", "expect"), ()),
}
EVIDENCE_KEYS = ("label", "model", "target", "fields")
EVIDENCE_OPTIONAL = ("screenshot", "company")

PASS, FAIL, ERROR, SKIPPED = "pass", "fail", "error", "skipped"
REQUIRES_STEP = "requires"
IDENTITIES_STEP = "identities"
USER_KEYS = ("login", "groups")
USER_OPTIONAL = ("companies",)

_TRACE_RE = re.compile(r"Traceback \(most recent call last\).*", re.S)
_PATH_RE = re.compile(r"(?:[A-Za-z]:)?/(?:home|Users|root|tmp|opt|srv|usr|var)/\S*")


def _bad(where, msg):
    return ValidationError("BAD_SCENARIO", f"{where}: {msg}")


def _check_keys(obj, where, required, optional):
    if not isinstance(obj, dict):
        raise _bad(where, "must be an object")
    missing = [k for k in required if k not in obj]
    if missing:
        raise _bad(where, f"missing {', '.join(missing)}")
    unknown = sorted(set(obj) - set(required) - set(optional))
    if unknown:
        raise _bad(where, f"unknown key {', '.join(unknown)}")


def _check_str(value, where, pattern=None):
    if not isinstance(value, str) or not value.strip():
        raise _bad(where, "must be a non-empty string")
    if pattern is not None and not pattern.match(value):
        raise _bad(where, f"{value!r} does not match {pattern.pattern}")


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_op_object(obj, where):
    if not isinstance(obj, dict) or not obj:
        raise _bad(where, f"must be a non-empty object of operators ({', '.join(OPS)})")
    for op, value in obj.items():
        if op not in OPS:
            raise _bad(where, f"unknown operator {op!r}")
        if op in ("in", "not_in") and not isinstance(value, list):
            raise _bad(f"{where}.{op}", "must be a list")


def _check_expect(expect, where, allowed):
    _check_keys(expect, where, (), allowed)
    if not expect:
        raise _bad(where, "is empty")
    if "count" in expect:
        count = expect["count"]
        if not _is_int(count):
            _check_op_object(count, f"{where}.count")
    if "fields" in expect:
        fields = expect["fields"]
        if not isinstance(fields, dict) or not fields:
            raise _bad(f"{where}.fields", "must be a non-empty object {field: {op: value}}")
        for name, ops in fields.items():
            _check_str(name, f"{where}.fields key")
            _check_op_object(ops, f"{where}.fields.{name}")


def _check_company(value, where):
    if not (isinstance(value, dict) and len(value) == 1 and next(iter(value)) in ("$ref", "$var", "$search")):
        raise _bad(where, 'must be one {"$ref"}, {"$var"} or {"$search"} naming a res.company')


def _check_ref(value, where, what):
    if not (isinstance(value, dict) and len(value) == 1 and next(iter(value)) in ("$ref", "$var", "$search")):
        raise _bad(where, f'must be one {{"$ref"}}, {{"$var"}} or {{"$search"}} naming {what}')


def _check_as(value, where, user_names):
    if isinstance(value, str):
        if value not in user_names:
            raise _bad(where, f"{value!r} is not declared in users")
        return
    _check_ref(value, where, "a res.users test user")


def _check_users(users, where):
    if not isinstance(users, dict) or not users:
        raise _bad(where, "must be a non-empty object {name: {login, groups, companies}}")
    logins = set()
    for name, user in users.items():
        at = f"{where}.{name}"
        _check_str(name, f"{where} key", VAR_RE)
        _check_keys(user, at, USER_KEYS, USER_OPTIONAL)
        if not identities.is_test_login(user["login"]):
            raise _bad(f"{at}.login", f"must be a test user: {', '.join(identities.LOGINS)}")
        if user["login"] in logins:
            raise _bad(f"{at}.login", f"{user['login']} is declared twice")
        logins.add(user["login"])
        for key in ("groups",) + (("companies",) if "companies" in user else ()):
            items = user[key]
            if not isinstance(items, list) or not items:
                raise _bad(f"{at}.{key}", "must be a non-empty list")
            for i, item in enumerate(items):
                _check_ref(item, f"{at}.{key}[{i}]", "a record")


def _check_steps(steps, where, seen_ids, user_names=()):
    if not isinstance(steps, list) or not steps:
        raise _bad(where, "must be a non-empty list")
    for i, step in enumerate(steps):
        at = f"{where}[{i}]"
        if not isinstance(step, dict):
            raise _bad(at, "must be an object")
        action = step.get("action")
        if action not in ACTIONS:
            raise _bad(at, f"action must be one of {', '.join(ACTIONS)}")
        required, optional = ACTIONS[action]
        _check_keys(step, at, STEP_COMMON + required, optional + STEP_OPTIONAL)
        _check_str(step["id"], f"{at}.id", ID_RE)
        if step["id"] in seen_ids:
            raise _bad(at, f"duplicate step id {step['id']!r}")
        if step["id"] in (REQUIRES_STEP, IDENTITIES_STEP):
            raise _bad(at, f"step id {step['id']!r} is reserved")
        seen_ids.add(step["id"])
        _check_str(step["model"], f"{at}.model")
        at = f"{where}[{step['id']}]"
        if "company" in step:
            _check_company(step["company"], f"{at}.company")
        if "as" in step:
            _check_as(step["as"], f"{at}.as", user_names)
        if "values" in step and not isinstance(step["values"], dict):
            raise _bad(f"{at}.values", "must be an object")
        if "domain" in step and not isinstance(step["domain"], list):
            raise _bad(f"{at}.domain", "must be a list")
        if "limit" in step and (not _is_int(step["limit"]) or step["limit"] < 1):
            raise _bad(f"{at}.limit", "must be a positive integer")
        if "method" in step:
            _check_str(step["method"], f"{at}.method")
        if "params" in step and not isinstance(step["params"], dict):
            raise _bad(f"{at}.params", "must be an object")
        if "wizards" in step:
            wiz = step["wizards"]
            if not isinstance(wiz, dict) or not all(isinstance(v, str) and v for v in wiz.values()):
                raise _bad(f"{at}.wizards", "must be an object {wizard model: method}")
        if "fields" in step:
            if not isinstance(step["fields"], list) or not step["fields"] or \
                    not all(isinstance(f, str) and f for f in step["fields"]):
                raise _bad(f"{at}.fields", "must be a non-empty list of field names")
        if "save_as" in step:
            _check_str(step["save_as"], f"{at}.save_as", VAR_RE)
        if "expect" in step:
            allowed = {"search": ("count",), "read": ("count", "fields"), "assert": ("count", "fields")}[action]
            _check_expect(step["expect"], f"{at}.expect", allowed)
            if action == "assert" and "fields" not in step["expect"]:
                raise _bad(f"{at}.expect", "assert needs expect.fields")


def validate(scenario, where="scenario"):
    """Raise ValidationError("BAD_SCENARIO") unless `scenario` follows C8."""
    _check_keys(scenario, where, TOP_REQUIRED, TOP_OPTIONAL)
    if scenario["format"] != FORMAT:
        raise _bad(f"{where}.format", f"must be {FORMAT!r}")
    _check_str(scenario["id"], f"{where}.id", ID_RE)
    if scenario["area"] not in AREAS:
        raise _bad(f"{where}.area", f"must be one of {', '.join(AREAS)}")
    _check_str(scenario["odoo_version"], f"{where}.odoo_version")
    if scenario["edition"] not in EDITIONS:
        raise _bad(f"{where}.edition", f"must be one of {', '.join(EDITIONS)}")
    _check_str(scenario["description"], f"{where}.description")
    if "requires" in scenario:
        req = scenario["requires"]
        _check_keys(req, f"{where}.requires", (), ("modules",))
        mods = req.get("modules", [])
        if not isinstance(mods, list) or not all(isinstance(m, str) and m for m in mods):
            raise _bad(f"{where}.requires.modules", "must be a list of module names")
    if "company" in scenario:
        _check_company(scenario["company"], f"{where}.company")
    if "users" in scenario:
        _check_users(scenario["users"], f"{where}.users")
    user_names = tuple(scenario.get("users") or ())
    if "as" in scenario:
        _check_as(scenario["as"], f"{where}.as", user_names)
    seen = set()
    if "preconditions" in scenario:
        _check_steps(scenario["preconditions"], f"{where}.preconditions", seen, user_names)
    _check_steps(scenario["steps"], f"{where}.steps", seen, user_names)
    evidence = scenario.get("evidence", [])
    if not isinstance(evidence, list):
        raise _bad(f"{where}.evidence", "must be a list")
    labels = set()
    for i, item in enumerate(evidence):
        at = f"{where}.evidence[{i}]"
        _check_keys(item, at, EVIDENCE_KEYS, EVIDENCE_OPTIONAL)
        _check_str(item["label"], f"{at}.label")
        if item["label"] in labels:
            raise _bad(at, f"duplicate label {item['label']!r}")
        labels.add(item["label"])
        _check_str(item["model"], f"{at}.model")
        if not isinstance(item["fields"], list) or not item["fields"] or \
                not all(isinstance(f, str) and f for f in item["fields"]):
            raise _bad(f"{at}.fields", "must be a non-empty list of field names")
        if "screenshot" in item and not isinstance(item["screenshot"], bool):
            raise _bad(f"{at}.screenshot", "must be true or false")
        if "company" in item:
            _check_company(item["company"], f"{at}.company")
    return scenario


def load(path):
    """Parse and validate one scenario file (C8) without running it.

    Returns the scenario dict; raises ValidationError on unreadable files,
    invalid JSON or any C8 rule.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValidationError("BAD_SCENARIO", f"{path.name}: cannot read ({e.strerror})") from None
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ValidationError("BAD_SCENARIO", f"{path.name}: not valid JSON ({e})") from None
    return validate(data, path.name)


# ---------------------------------------------------------------- running


def safe_message(exc):
    """A step message from an exception's name/message only, never a traceback or a path."""
    if isinstance(exc, OdooError):
        text = f"{exc.name}: {exc.message}" if exc.name else str(exc.message)
    elif isinstance(exc, OfaError):
        text = f"{exc.label}: {exc.msg}"
    else:
        text = type(exc).__name__
    return scrub(text)


def scrub(text):
    """Defence in depth: drop anything that looks like a traceback or an absolute path."""
    text = _TRACE_RE.sub("[traceback removed]", str(text))
    text = _PATH_RE.sub("<path>", text)
    return " ".join(text.split())[:500]


class StepFailed(Exception):
    """An expectation did not hold."""


def _ids(value, where):
    if _is_int(value):
        return [value]
    if isinstance(value, list) and value and all(_is_int(v) for v in value):
        return list(value)
    raise ValidationError("BAD_TARGET", f"{where}: target must resolve to a record id or a non-empty id list, got {value!r}")


def _cmp(op, actual, expected):
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "contains":
        if isinstance(actual, str):
            return isinstance(expected, str) and expected in actual
        if isinstance(actual, list):
            wanted = expected if isinstance(expected, list) else [expected]
            return all(w in actual for w in wanted)
        return False
    # gt gte lt lte: numbers only; Odoo's False for an empty value never compares.
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (actual, expected)):
        return False
    return {"gt": actual > expected, "gte": actual >= expected, "lt": actual < expected, "lte": actual <= expected}[op]


def check_ops(ops, actual, label):
    """Raise StepFailed naming the first operator in `ops` that `actual` does not satisfy."""
    for op, expected in ops.items():
        if not _cmp(op, actual, expected):
            hint = ""
            if op in ("eq", "ne") and _is_int(actual) and isinstance(expected, list) and len(expected) == 1:
                # T24: a `$var` set by a search holds a list of ids, while a many2one reads as one id.
                hint = "; the value is a one-id list (a search result) and the field holds one id: use in / not_in"
            raise StepFailed(f"{label}: expected {op} {json.dumps(expected, ensure_ascii=False)}, "
                             f"got {json.dumps(actual, ensure_ascii=False, default=str)}{hint}")


def _check_expect_live(client, expect, vars, count, rows, label_prefix=""):
    if "count" in expect:
        spec = expect["count"]
        check_ops({"eq": spec} if _is_int(spec) else refs.resolve(client, spec, vars), count, f"{label_prefix}count")
    for name, ops in (expect.get("fields") or {}).items():
        resolved = refs.resolve(client, ops, vars)
        for row in rows:
            check_ops(resolved, refs.normalize_read(row.get(name)), f"{label_prefix}{name} of id {row.get('id')}")


class _InCompany:
    """The client with `allowed_company_ids` set on every call, like a user who picked that company.

    A context the call passes itself (a wizard action's) is merged on top.
    """

    def __init__(self, client, company_id):
        self._client = client
        self._ctx = {"allowed_company_ids": [company_id]}

    def call(self, model, method, *, context=None, **kw):
        return self._client.call(model, method, context={**self._ctx, **(context or {})}, **kw)

    def __getattr__(self, name):
        return getattr(self._client, name)


def in_company(client, spec, vars, actor=None):
    """`client` itself when `spec` is None, else a client whose calls run in the company `spec` resolves to.

    `spec` is resolved with `client`; with `actor` given, that client (a test user's) is the one wrapped.
    """
    actor = client if actor is None else actor
    if spec is None:
        return actor
    company_id = refs.resolve(client, spec, vars)
    if not _is_int(company_id):
        raise ValidationError("BAD_TARGET", f"company must resolve to one res.company id, got {company_id!r}")
    return _InCompany(actor, company_id)


class _Identities:
    """The test users a scenario acts as (C8 `as`): their clients, and what the report says about each.

    The bot resolves every reference and sets up declared `users`; a step with `as` makes its calls with that
    user's own key, so Odoo applies that user's access rights, record rules and approval limits.
    """

    def __init__(self, bot, scenario):
        self.bot = bot
        self.declared = scenario.get("users") or {}
        self.uids = {}       # declared name -> uid
        self.clients = {}    # login -> client
        self.used = {}       # login -> {"login", "source", "groups"}

    def _role_key(self, uid):
        rows = self.bot.call("ir.model.data", "search_read",
                             domain=[["model", "=", identities.USERS_MODEL], ["res_id", "=", uid],
                                     ["module", "=", refs.OFA_MODULE]], fields=["name"], limit=1)
        return rows[0]["name"] if rows else None

    def _uid_of_login(self, login):
        found = self.bot.call(identities.USERS_MODEL, "search", domain=[["login", "=", login]], limit=1)
        if not found:
            raise EnvError("TEST_USER_MISSING", f"no {login} on {self.bot.target.db}; ofa reset {self.bot.target.name}")
        return found[0]

    def setup(self, vars):
        """Give each declared user exactly its groups (and companies). Only for users no plan role owns."""
        for name, user in self.declared.items():
            login = user["login"]
            uid = self._uid_of_login(login)
            key = self._role_key(uid)
            if key:
                raise ValidationError("TEST_USER_HAS_ROLE", f"{login} is the plan's role __ofa__.{key}; act as it "
                                      f'with "as": {{"$ref": "__ofa__.{key}"}} instead of declaring it in users')
            groups = [refs.resolve(self.bot, g, vars) for g in user["groups"]]
            identities.check_requested(self.bot, login, groups)
            vals = {"group_ids": [[6, 0, groups]]}
            if "companies" in user:
                companies = [refs.resolve(self.bot, c, vars) for c in user["companies"]]
                vals["company_ids"] = [[6, 0, companies]]
                vals["company_id"] = companies[0]
            self.bot.call(identities.USERS_MODEL, "write", ids=[uid], vals=vals)
            identities.check_held(self.bot, login, uid)
            self.uids[name] = uid

    def actor(self, spec, vars):
        """The client to call with for `as` = spec: None for the bot itself."""
        if spec is None:
            return None
        uid = self.uids[spec] if isinstance(spec, str) else refs.resolve(self.bot, spec, vars)
        if not _is_int(uid):
            raise ValidationError("BAD_TARGET", f"as must resolve to one res.users id, got {uid!r}")
        if uid == self.bot.bot_uid():
            return None
        login = identities.login_of(self.bot, uid)
        if login not in self.clients:
            self.clients[login] = clientmod.open_identity(self.bot, login)
            key = self._role_key(uid)
            source = (f"plan role __ofa__.{key}" if key
                      else "scenario users (assumption)" if isinstance(spec, str) else "provisioned, no role")
            self.used[login] = {**identities.describe(self.bot, uid), "source": source}
        return self.clients[login]

    def report(self):
        return [self.used[login] for login in sorted(self.used)]


def _run_step(client, step, vars, actor=None):
    """Run one step and return its {"model", "ids"} records. Raises StepFailed or OfaError.

    `client` resolves references; `actor` (default `client`) makes the step's own calls.
    """
    actor = client if actor is None else actor
    action, model = step["action"], step["model"]
    records = {"model": model, "ids": []}
    if action == "create":
        values = refs.resolve(client, step["values"], vars)
        new_ids = actor.call(model, "create", vals_list=[values])
        records["ids"] = list(new_ids)
        if "save_as" in step:
            vars[step["save_as"]] = new_ids[0]
        return records
    if action == "search":
        params = {"domain": refs.resolve(client, step["domain"], vars)}
        if "limit" in step:
            params["limit"] = step["limit"]
        found = actor.call(model, "search", **params)
        records["ids"] = list(found)
        if "save_as" in step:
            vars[step["save_as"]] = list(found)
        if "expect" in step:
            _check_expect_live(client, step["expect"], vars, len(found), [])
        return records
    ids = _ids(refs.resolve(client, step["target"], vars), step["id"])
    records["ids"] = ids
    if action == "write":
        actor.call(model, "write", ids=ids, vals=refs.resolve(client, step["values"], vars))
    elif action == "call":
        params = refs.resolve(client, step.get("params") or {}, vars)
        wizards.call_following(actor, model, step["method"], ids, params=params, wizards=step.get("wizards"))
    elif action in ("read", "assert"):
        fields = step["fields"] if action == "read" else list(step["expect"]["fields"])
        rows = actor.call(model, "read", ids=ids, fields=fields)
        if action == "read" and "save_as" in step:
            vars[step["save_as"]] = rows
        if "expect" in step:
            _check_expect_live(client, step["expect"], vars, len(rows), rows)
    return records


def _run_steps(client, steps, vars, failure_status, company=None, users=None, as_=None):
    """Run steps until the first failure. Returns (status, results).

    `company` and `as_` are the scenario-level specs; a step's own `company` and `as` override them.
    `users` is the scenario's _Identities.
    """
    results = []
    status = PASS
    for step in steps:
        if status != PASS:
            results.append({"id": step["id"], "status": SKIPPED, "message": "", "records": {"model": step["model"], "ids": []}})
            continue
        try:
            spec = step.get("company", company)
            user = users.actor(step.get("as", as_), vars) if users else None
            resolver = in_company(client, spec, vars)
            records = _run_step(resolver, step, vars, in_company(client, spec, vars, user) if user else None)
            results.append({"id": step["id"], "status": PASS, "message": "", "records": records})
        except StepFailed as e:
            status = failure_status
            results.append({"id": step["id"], "status": status, "message": scrub(str(e)), "records": _last_records(step, vars)})
        except (EnvError, GuardError) as e:
            status = ERROR
            results.append({"id": step["id"], "status": ERROR, "message": safe_message(e), "records": _last_records(step, vars)})
        except OfaError as e:
            status = failure_status
            results.append({"id": step["id"], "status": status, "message": safe_message(e), "records": _last_records(step, vars)})
    return status, results


def _last_records(step, vars):
    ids = []
    target = step.get("target")
    if isinstance(target, dict) and "$var" in target:
        value = vars.get(target["$var"])
        if _is_int(value):
            ids = [value]
        elif isinstance(value, list) and all(_is_int(v) for v in value):
            ids = list(value)
    return {"model": step["model"], "ids": ids}


def _check_requires(client, scenario):
    """Return an error message when the target cannot run this scenario, else None."""
    target = client.target
    if scenario["odoo_version"] != target.odoo_version:
        return f"scenario is for Odoo {scenario['odoo_version']}, target {target.name} is {target.odoo_version}"
    if scenario["edition"] == "enterprise" and target.edition != "enterprise":
        return f"scenario needs enterprise, target {target.name} is {target.edition}"
    mods = sorted(set((scenario.get("requires") or {}).get("modules", [])))
    if mods:
        rows = client.call("ir.module.module", "search_read",
                           domain=[["name", "in", mods], ["state", "=", "installed"]], fields=["name"])
        missing = sorted(set(mods) - {r["name"] for r in rows})
        if missing:
            return f"modules not installed: {', '.join(missing)}"
    return None


def run(client, scenario):
    """Run one validated scenario. Returns (result, evidence_records, screenshot_targets).

    result = {"id", "status", "steps": [{"id", "status", "message", "records"}]} (C9).
    """
    vars = {}
    steps_out = []
    status = PASS
    try:
        problem = _check_requires(client, scenario)
    except OfaError as e:
        problem = safe_message(e)
    if problem:
        status = ERROR
        steps_out.append({"id": REQUIRES_STEP, "status": ERROR, "message": scrub(problem), "records": {"model": "", "ids": []}})
    users = _Identities(client, scenario)
    if status == PASS and users.declared:
        try:
            users.setup(vars)
        except OfaError as e:
            status = ERROR
            steps_out.append({"id": IDENTITIES_STEP, "status": ERROR, "message": safe_message(e),
                              "records": {"model": identities.USERS_MODEL, "ids": []}})
    scope = {"company": scenario.get("company"), "users": users, "as_": scenario.get("as")}
    if status == PASS and scenario.get("preconditions"):
        # A failing precondition means the scenario could not be set up: error, not fail.
        status, results = _run_steps(client, scenario["preconditions"], vars, ERROR, **scope)
        steps_out += results
    if status == PASS:
        status, results = _run_steps(client, scenario["steps"], vars, FAIL, **scope)
        steps_out += results
    else:
        done = {s["id"] for s in steps_out}
        steps_out += [{"id": s["id"], "status": SKIPPED, "message": "", "records": {"model": s["model"], "ids": []}}
                      for s in (scenario.get("preconditions") or []) + scenario["steps"] if s["id"] not in done]
    evidence, shots = ({}, []) if status == ERROR else collect_evidence(client, scenario, vars)
    result = {"id": scenario["id"], "status": status, "steps": steps_out}
    if users.used:
        result["identities"] = users.report()
    return result, evidence, shots


def screenshot_url(base_url, model, res_id):
    return f"{base_url.rstrip('/')}/odoo/{model}/{res_id}"


def collect_evidence(client, scenario, vars):
    """Read back every evidence item. Returns ({label: rows | {"error"}}, screenshot targets)."""
    out, shots = {}, []
    for item in scenario.get("evidence", []):
        label, model = item["label"], item["model"]
        try:
            reader = in_company(client, item.get("company", scenario.get("company")), vars)
            ids = _ids(refs.resolve(reader, item["target"], vars), f"evidence {label}")
            rows = reader.call(model, "read", ids=ids, fields=list(item["fields"]))
        except OfaError as e:
            out[label] = {"error": safe_message(e)}
            continue
        out[label] = [{k: v for k, v in row.items() if k == "id" or k in item["fields"]} for row in rows]
        if item.get("screenshot"):
            shots += [{"scenario": scenario["id"], "label": label, "model": model, "id": i,
                       "url": screenshot_url(client.target.url, model, i)} for i in ids]
    return out, shots
