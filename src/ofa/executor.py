"""Idempotent apply of a frozen plan against a demo target (C7)."""
import json
import math
import re
import time
from pathlib import Path

from ofa import plan as planmod
from ofa import refs, wizards
from ofa.errors import OdooError, OfaError, ValidationError

MODULE_MODEL = "ir.module.module"
SETTINGS_MODEL = "res.config.settings"
COMPANY_MODEL = "res.company"
DB_UUID_KEY = "database.uuid"

_TRACEBACK = "Traceback (most recent call last)"
# Absolute filesystem paths (two segments or more), but not the path part of a URL.
_PATH_RE = re.compile(r"(?<![\w.:/~-])/(?:[\w.@+-]+/)+[\w.@+-]*")


def safe_error(exc):
    """`<name>: <message>` from the exception only: no traceback, no filesystem path."""
    if isinstance(exc, OdooError):
        text = f"{exc.name}: {exc.message}" if exc.name else f"HTTP {exc.status}: {exc.message}"
    elif isinstance(exc, OfaError):
        text = f"{exc.label}: {exc.msg}"
    else:
        text = f"internal {type(exc).__name__}: {exc}"
    text = text.split(_TRACEBACK, 1)[0].rstrip()
    return _PATH_RE.sub("<path>", text)


def _context(client, op):
    company = op.get("company")
    if company is None:
        return None
    return {"allowed_company_ids": [refs.resolve(client, company, {})]}


def _same(want, have):
    """Does the read-back value `have` already hold the resolved write value `want`?"""
    have = refs.normalize_read(have)
    if isinstance(want, list) and want and all(isinstance(c, list) and c and c[0] in (4, 6) for c in want):
        current = set(have) if isinstance(have, list) else set()
        if want[0][0] == 6 and len(want) == 1:
            return current == set(want[0][2])
        if all(c[0] == 4 for c in want):
            return {c[1] for c in want} <= current
        return False
    if want in (None, False) and have in (None, False):
        return True
    if isinstance(want, float) or isinstance(have, float):
        if isinstance(want, (int, float)) and isinstance(have, (int, float)) and not isinstance(want, bool):
            return math.isclose(want, have, rel_tol=0, abs_tol=1e-9)
    if isinstance(want, list) and isinstance(have, list):
        return sorted(map(json.dumps, want)) == sorted(map(json.dumps, have))
    return want == have


def _diff(client, model, res_id, values, ctx):
    rows = client.call(model, "read", ids=[res_id], fields=sorted(values), context=ctx)
    if not rows:
        raise ValidationError("RECORD_MISSING", f"{model} {res_id} cannot be read")
    row = rows[0]
    return {k: v for k, v in values.items() if not _same(v, row.get(k))}


def _install_modules(client, op, ctx):
    names = op["modules"]
    rows = client.call(MODULE_MODEL, "search_read", domain=[["name", "in", names]], fields=["name", "state"], context=ctx)
    found = {r["name"]: r for r in rows}
    missing = [n for n in names if n not in found]
    if missing:
        raise ValidationError("UNKNOWN_MODULE", f"not available on the target: {', '.join(missing)}")
    todo = [found[n]["id"] for n in names if found[n]["state"] != "installed"]
    if not todo:
        return "unchanged", [found[n]["id"] for n in names]
    client.call(MODULE_MODEL, "button_immediate_install", ids=todo, context=ctx)
    return "created", todo


def _set_settings(client, op, ctx):
    values = refs.resolve(client, op["values"], {})
    probe = client.call(SETTINGS_MODEL, "create", vals_list=[{}], context=ctx)[0]
    if not _diff(client, SETTINGS_MODEL, probe, values, ctx):
        return "unchanged", [probe]
    sid = client.call(SETTINGS_MODEL, "create", vals_list=[values], context=ctx)[0]
    client.call(SETTINGS_MODEL, "execute", ids=[sid], context=ctx)
    return "updated", [sid]


def _grant_company(client, company_id):
    # S2 F3: the bot must be a member of every company the plan creates.
    client.call("res.users", "write", ids=[client.bot_uid()], vals={"company_ids": [[4, company_id]]})


def _upsert_record(client, op, ctx):
    model, key = op["model"], op["key"]
    values = refs.resolve(client, op["values"], {})
    found = refs.lookup_ofa(client, key)
    if found is not None:
        found_model, res_id = found
        if found_model != model:
            raise ValidationError("KEY_MODEL_MISMATCH", f"__ofa__.{key} points to {found_model}, not {model}")
        diff = _diff(client, model, res_id, values, ctx)
        if not diff:
            return "unchanged", [res_id]
        client.call(model, "write", ids=[res_id], vals=diff, context=ctx)
        return "updated", [res_id]
    match = op.get("match")
    if match:
        ids = client.call(model, "search", domain=refs.resolve(client, match, {}), limit=2, context=ctx)
        if len(ids) > 1:
            raise ValidationError("MATCH_NOT_UNIQUE", f"match finds more than one {model}; make it stricter")
        if len(ids) == 1:
            res_id = ids[0]
            refs.store_ofa(client, key, model, res_id)
            diff = _diff(client, model, res_id, values, ctx)
            if diff:
                client.call(model, "write", ids=[res_id], vals=diff, context=ctx)
            return "adopted", [res_id]
    res_id = client.call(model, "create", vals_list=[values], context=ctx)[0]
    refs.store_ofa(client, key, model, res_id)
    if model == COMPANY_MODEL:
        _grant_company(client, res_id)
    return "created", [res_id]


def _call_method(client, op, ctx):
    target = refs.resolve(client, op["target"], {})
    ids = target if isinstance(target, list) else [target]
    skip = refs.resolve(client, op["skip_if"], {})
    count = client.call(skip["model"], "search_count", domain=skip["domain"], context=ctx)
    if count >= skip.get("min_count", 1):
        return "unchanged", ids
    params = refs.resolve(client, op.get("params") or {}, {})
    wizards.call_following(client, op["model"], op["method"], ids, params=params, context=ctx,
                           wizards=op.get("wizards"))
    return "called", ids


HANDLERS = {
    "install_modules": (_install_modules, lambda op: MODULE_MODEL),
    "set_settings": (_set_settings, lambda op: SETTINGS_MODEL),
    "upsert_record": (_upsert_record, lambda op: op["model"]),
    "call_method": (_call_method, lambda op: op["model"]),
}


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _db_uuid(client):
    try:
        return client.call("ir.config_parameter", "get_str", key=DB_UUID_KEY) or ""
    except OdooError:
        return ""


def is_first_apply(plan_dir, target, db, db_uuid):
    """True unless an earlier run of this plan dir hit the same database.

    The database is identified by name and `database.uuid`, which provisioning
    regenerates, so a reset DB counts as fresh again.
    """
    for path in sorted((Path(plan_dir) / "runs").glob("*/apply.json")):
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if prior.get("target") == target and prior.get("db") == db and prior.get("db_uuid", "") == db_uuid:
            return False
    return True


PRODUCING = ("created", "updated", "adopted")


def ofa_keys(op):
    """The `__ofa__` keys an op refers to anywhere (target, match, values, params, skip_if...)."""
    prefix = refs.OFA_MODULE + "."
    return {r[len(prefix):] for r in planmod.ref_names(op) if r.startswith(prefix)}


class RunState:
    """Which `__ofa__` keys this run produced, to tell pre-existing state from the run's own effect.

    A key is produced when its upsert op is created/updated/adopted, or when that op itself
    depends on a produced key (so the dependency carries through chains of refs).
    """

    def __init__(self):
        self.produced = set()

    def depends_on_run(self, op):
        return bool(ofa_keys(op) & self.produced)

    def record(self, op, status):
        dependent = self.depends_on_run(op)
        if op.get("type") == "upsert_record" and (status in PRODUCING or dependent):
            self.produced.add(op.get("key"))
        return dependent


def produced_in_run(plan, record):
    """Op ids whose result depends on state an earlier op of the same run produced."""
    status = {o["op_id"]: o["status"] for o in record["ops"]}
    state = RunState()
    out = set()
    for op in planmod.order(plan):
        if op["id"] in status and state.record(op, status[op["id"]]):
            out.add(op["id"])
    return out


def _new_run_dir(plan_dir, target_name, clock, sleep):
    runs = Path(plan_dir) / "runs"
    runs.mkdir(exist_ok=True)
    for _ in range(3):
        started = clock()
        run_id = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(started))}_{target_name}"
        try:
            (runs / run_id).mkdir()
            return run_id, runs / run_id, started
        except FileExistsError:
            sleep(1.0 - started % 1.0 + 0.01)
    raise ValidationError("RUN_ID_TAKEN", f"cannot allocate a run id under {runs}")


def run(client, plan, plan_dir, sha256, *, clock=time.time, sleep=time.sleep):
    """Apply every op in topological order and write runs/<run_id>/apply.json. Returns the record."""
    target = client.target
    run_id, run_dir, started = _new_run_dir(plan_dir, target.name, clock, sleep)
    db_uuid = _db_uuid(client)
    first = is_first_apply(plan_dir, target.name, target.db, db_uuid)
    results = []
    failed = False
    state = RunState()
    for op in planmod.order(plan):
        handler, model_of = HANDLERS[op["type"]]
        rec = {"op_id": op["id"], "type": op["type"], "status": "skipped", "model": model_of(op),
               "res_ids": [], "pre_state": False, "error": None, "duration_ms": 0}
        results.append(rec)
        if failed:
            continue
        t0 = time.monotonic()
        try:
            status, res_ids = handler(client, op, _context(client, op))
            dependent = state.record(op, status)
            # S2 F1: flag only state that held before this plan; not what an earlier op of this run made.
            rec.update(status=status, res_ids=list(res_ids),
                       pre_state=first and status == "unchanged" and not dependent)
        except Exception as e:  # noqa: BLE001 - every failure is recorded, then the run stops
            rec.update(status="failed", error=safe_error(e))
            failed = True
        rec["duration_ms"] = round((time.monotonic() - t0) * 1000)
    record = {
        "run_id": run_id, "plan_sha256": sha256, "target": target.name, "db": target.db,
        "db_uuid": db_uuid, "odoo_version": target.odoo_version, "edition": target.edition,
        "started_at": _iso(started), "finished_at": _iso(clock()), "ops": results,
    }
    tmp = run_dir / ".apply.json.tmp"
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(run_dir / "apply.json")
    return record


def has_failure(record):
    return any(op["status"] == "failed" for op in record["ops"])
