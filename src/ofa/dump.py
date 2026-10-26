"""`ofa dump`: a canonical, id-free JSON view of what a plan configured (C10).

Two databases whose dumps are byte-identical hold the same configuration (R7).
plan.json is read with plain json.load (C6 shape); this module does not depend
on ofa.plan.
"""
import json
from pathlib import Path

from ofa import refs
from ofa.errors import ValidationError

PLAN_FORMAT = "ofa.plan/1"
DROPPED = frozenset({"id", "create_date", "write_date", "create_uid", "write_uid"})
RELATIONAL = frozenset({"many2one", "one2many", "many2many"})
# Exported xmlids carry generated suffixes that differ across databases.
UNSTABLE_MODULES = frozenset({"__export__"})
SETTINGS_MODEL = "res.config.settings"


def load_plan(plan_dir):
    path = Path(plan_dir) / "plan.json"
    try:
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
    except OSError as e:
        raise ValidationError("BAD_PLAN", f"cannot read plan.json ({e.strerror})") from None
    except ValueError as e:
        raise ValidationError("BAD_PLAN", f"plan.json is not valid JSON ({e})") from None
    if not isinstance(plan, dict) or plan.get("format") != PLAN_FORMAT or not isinstance(plan.get("operations"), list):
        raise ValidationError("BAD_PLAN", f"plan.json is not an {PLAN_FORMAT} plan with an operations list")
    for op in plan["operations"]:
        if not isinstance(op, dict) or not isinstance(op.get("id"), str) or not isinstance(op.get("type"), str):
            raise ValidationError("BAD_PLAN", "every operation needs an id and a type")
        if op["type"] == "upsert_record" and not isinstance(op.get("key"), str):
            raise ValidationError("BAD_PLAN", f"{op['id']}: upsert_record needs a key")
    return plan


def canonical(data):
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


class Normalizer:
    """Replaces relational ids by stable names, caching per (model, id)."""

    def __init__(self, client):
        self.client = client
        self._field_types = {}
        self._names = {}

    def field_types(self, model, names):
        missing = [n for n in names if (model, n) not in self._field_types]
        if missing:
            described = self.client.call(model, "fields_get", allfields=missing, attributes=["type", "relation"])
            for n in missing:
                info = described.get(n) or {}
                self._field_types[(model, n)] = (info.get("type"), info.get("relation"))
        return {n: self._field_types[(model, n)] for n in names}

    def names(self, model, ids):
        """{id: "module.name" | "<model>:<display_name>"} for ids of `model`."""
        todo = sorted({i for i in ids if (model, i) not in self._names})
        if todo:
            rows = self.client.call("ir.model.data", "search_read",
                                    domain=[["model", "=", model], ["res_id", "in", todo]],
                                    fields=["module", "name", "res_id"])
            best = {}
            for r in rows:
                if r["module"] in UNSTABLE_MODULES:
                    continue
                xmlid = f"{r['module']}.{r['name']}"
                # Prefer the plan's own __ofa__ key, then the smallest name, so the choice is deterministic.
                rank = (r["module"] != refs.OFA_MODULE, xmlid)
                if r["res_id"] not in best or rank < best[r["res_id"]][0]:
                    best[r["res_id"]] = (rank, xmlid)
            for i, (_, xmlid) in best.items():
                self._names[(model, i)] = xmlid
            rest = [i for i in todo if i not in best]
            if rest:
                for row in self.client.call(model, "read", ids=rest, fields=["display_name"]):
                    self._names[(model, row["id"])] = f"{model}:{row.get('display_name')}"
                for i in rest:
                    self._names.setdefault((model, i), f"{model}:<missing>")
        return {i: self._names[(model, i)] for i in ids}

    def value(self, ftype, relation, raw):
        if ftype not in RELATIONAL or not relation:
            return raw
        if raw is False or raw is None or raw == []:
            return [] if ftype != "many2one" else None
        norm = refs.normalize_read(raw)
        if ftype == "many2one":
            return self.names(relation, [norm])[norm]
        ids = norm if isinstance(norm, list) else [norm]
        return sorted(self.names(relation, ids).values())

    def row(self, model, row, fields):
        types = self.field_types(model, fields)
        return {f: self.value(*types[f], row.get(f)) for f in fields}


def _plan_fields(values):
    return sorted(k for k in (values or {}) if k not in DROPPED)


def _company_context(client, op):
    company = op.get("company")
    if company is None:
        return None
    cid = refs.resolve(client, company, {})
    return {"allowed_company_ids": [cid]}


def dump(client, plan):
    """Return the C10 dump dict for `plan` as configured in the client's database."""
    norm = Normalizer(client)
    ops = plan["operations"]
    wanted = sorted({m for op in ops if op["type"] == "install_modules" for m in op.get("modules") or []})
    modules = []
    if wanted:
        rows = client.call("ir.module.module", "search_read",
                           domain=[["name", "in", wanted], ["state", "=", "installed"]], fields=["name"])
        modules = sorted({r["name"] for r in rows})

    settings = {}
    for op in ops:
        if op["type"] != "set_settings":
            continue
        fields = _plan_fields(op.get("values"))
        ctx = _company_context(client, op)
        sid = client.call(SETTINGS_MODEL, "create", vals_list=[{}], context=ctx)[0]
        row = client.call(SETTINGS_MODEL, "read", ids=[sid], fields=fields, context=ctx)[0]
        settings[op["id"]] = norm.row(SETTINGS_MODEL, row, fields)

    records = {}
    for op in ops:
        if op["type"] != "upsert_record":
            continue
        xmlid = f"{refs.OFA_MODULE}.{op['key']}"
        found = refs.lookup_ofa(client, op["key"])
        if found is None:
            records[xmlid] = {"model": op.get("model"), "values": None}
            continue
        model, res_id = found
        fields = _plan_fields(op.get("values"))
        rows = client.call(model, "read", ids=[res_id], fields=fields) if fields else [{}]
        records[xmlid] = {"model": model, "values": norm.row(model, rows[0], fields) if rows else None}
    return {"modules": modules, "settings": settings, "records": records}
