"""ofa lint-plan: check every identifier a plan names, in plan.json and in plan.md's prose (T18, S6).

S6 found that the identifiers a plan gets wrong are names written from memory of older Odoo versions, and
that both errors of its measured set were in plan.md, not in plan.json. So the linter checks both:

- plan.json: modules, models, value keys, settings keys, domain fields, methods, `$ref` xmlids and
  selection values;
- plan.md: every dotted name inside backticks (`model`, `model.field`, `model.method()`, `module.xmlid`).

The live target is the authority. It reads `ir.module.module`, `ir.model`, `ir.model.fields` (not
`fields_get`, which hides group-restricted fields) and `ir.model.data`. A name the live database does not
have is looked up in the static source index (`ofa.source_index`), because the linter runs before the
plan's modules are installed:

- `ok` (static): defined by a module the plan installs, or one that comes with it (dependencies,
  auto_install);
- `NEEDS_MODULE`: defined only by modules the plan does not install;
- `NOT_IN_20`: defined nowhere in the 20.0 source.
"""
import re
from dataclasses import dataclass, field

from ofa import plan as planmod
from ofa import refs

SETTINGS = "res.config.settings"
IGNORE_RE = re.compile(r"<!--\s*ofa-lint-ignore:\s*(.*?)\s*-->", re.S)
FENCE_RE = re.compile(r"^```.*?^```", re.S | re.M)
SPAN_RE = re.compile(r"`([^`\n]+)`")
DOTTED_RE = re.compile(r"(?<![\w.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(\(\))?")
# A bare name is checked only when it looks like a technical name: lowercase snake_case with an underscore.
SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
WORD_RE = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?![\w.(])")
# Dotted words outside backticks that are not Odoo names: file names, hosts.
_NOT_NAME_SUFFIX = re.compile(r"\.(md|py|xml|json|csv|js|html|txt|com|org|io|toml|po|pot)$")
_WORDS_IGNORED = {"True", "False", "None", "and", "or", "not", "in", "is", "if", "else", "for", "self"}


# In plan.md a name from a module the plan does not install can be a legitimate mention (an alternative
# the plan rejects), so there it is a warning; everything else, and anything in plan.json, is an error.
PROSE_WARNINGS = {"NEEDS_MODULE"}


@dataclass
class Problem:
    where: str
    code: str
    name: str
    detail: str

    @property
    def severity(self):
        return "warning" if self.where.startswith("plan.md") and self.code in PROSE_WARNINGS else "error"

    def line(self):
        return f"{self.where}: {self.code}: {self.name}: {self.detail}" + (
            " (warning)" if self.severity == "warning" else "")


@dataclass
class Result:
    problems: list = field(default_factory=list)
    json_checked: int = 0
    json_static: int = 0
    md_checked: int = 0
    md_static: int = 0
    md_unchecked: dict = field(default_factory=lambda: {"bare_names": 0, "path_spans": 0, "not_identifiers": 0,
                                                       "outside_backticks": 0, "fenced_blocks": 0, "ignored": 0,
                                                       "own_names": 0, "custom_fields": 0})

    def add(self, where, code, name, detail):
        self.problems.append(Problem(where, code, name, detail))

    @property
    def errors(self):
        return [p for p in self.problems if p.severity == "error"]


class Live:
    """What the target database has, read once and cached."""

    def __init__(self, client):
        self.client = client
        rows = client.call("ir.module.module", "search_read", domain=[], fields=["name", "state"])
        self.module_state = {r["name"]: r["state"] for r in rows}
        self.models = {r["model"] for r in client.call("ir.model", "search_read", domain=[], fields=["model"])}
        self._fields = {}
        self._selection = {}
        self._xmlids = {}

    def installed(self):
        return {m for m, s in self.module_state.items() if s == "installed"}

    def fields(self, model):
        if model not in self._fields:
            rows = self.client.call("ir.model.fields", "search_read", domain=[["model", "=", model]],
                                    fields=["name", "ttype", "relation"]) if model in self.models else []
            self._fields[model] = {r["name"]: r for r in rows}
        return self._fields[model]

    def selection(self, model, name):
        key = (model, name)
        if key not in self._selection:
            rows = self.client.call("ir.model.fields.selection", "search_read",
                                    domain=[["field_id.model", "=", model], ["field_id.name", "=", name]],
                                    fields=["value"])
            self._selection[key] = {r["value"] for r in rows}
        return self._selection[key]

    def xmlid(self, full):
        if full not in self._xmlids:
            module, _, name = full.partition(".")
            rows = self.client.call("ir.model.data", "search_read",
                                    domain=[["module", "=", module], ["name", "=", name]], fields=["model"])
            self._xmlids[full] = rows[0]["model"] if rows else None
        return self._xmlids[full]


class Checker:
    def __init__(self, live, index, plan, edition):
        self.live = live
        self.index = index
        self.edition = edition
        self.plan_modules = sorted({m for op in planmod.operations(plan) if op.get("type") == "install_modules"
                                    for m in op.get("modules", [])})
        self.effective = index.closure(live.installed() | set(self.plan_modules))
        self.plan_keys = set(planmod.upsert_keys(plan))
        self.own_names = set()

    def add_own_names(self, names):
        """Names that belong to the plan or to ofa, not to Odoo (targets, keys, op ids, scenario ids...)."""
        self.own_names |= set(names)

    # -- classification of a name the live DB lacks -------------------------------------------------------
    def _static(self, modules, name, what, where, result):
        """Classify `name` from the modules the source index says define it. True when acceptable."""
        if modules & self.effective:
            ee = {m for m in modules & self.effective if self.index.modules.get(m, {}).get("edition") == "enterprise"}
            if self.edition == "community" and ee == modules & self.effective:
                result.add(where, "EDITION", name, f"{what} only in Enterprise modules ({', '.join(sorted(ee))})")
                return False
            return True
        if modules:
            result.add(where, "NEEDS_MODULE", name,
                       f"{what} exists only in {', '.join(sorted(modules)[:5])}, which the plan does not install")
        else:
            result.add(where, "NOT_IN_20", name, f"{what} does not exist in Odoo 20.0")
        return False

    def model(self, model, where, result):
        if model in self.live.models:
            return "live"
        return "static" if self._static(self.index.model_modules(model), model, "model", where, result) else None

    def has_model(self, model):
        return model in self.live.models or bool(self.index.model_modules(model))

    def member(self, model, name):
        """('field'|'method', live?) for a name of `model`, or None when it is neither anywhere."""
        if name in self.live.fields(model):
            return "field", True
        if self.index.field_modules(model, name):
            return "field", False
        if self.index.method_modules(model, name):
            return "method", False
        return None

    def field(self, model, name, where, result, label=None):
        label = label or f"{model}.{name}"
        if self.model(model, where, result) is None:
            return None
        if name in ("id", "display_name", "create_date", "write_date", "create_uid", "write_uid"):
            return "live"
        if name in self.live.fields(model):
            return "live"
        return "static" if self._static(self.index.field_modules(model, name), label, "field", where, result) else None

    def relation(self, model, name):
        info = self.live.fields(model).get(name)
        if info:
            return info.get("relation") or None
        info = self.index.field_info(model, name)
        return info and info.get("comodel")

    def path(self, model, dotted, where, result):
        """A domain path `a.b.c` from `model`: every hop must exist. Returns the final status."""
        status = "live"
        for i, part in enumerate(dotted.split(".")):
            got = self.field(model, part, where, result, label=f"{model}.{part}")
            if got is None:
                return None
            status = "static" if got == "static" else status
            if i < len(dotted.split(".")) - 1:
                model = self.relation(model, part)
                if not model:
                    return status
        return status

    def method(self, model, name, where, result):
        if self.model(model, where, result) is None:
            return None
        return "static" if self._static(self.index.method_modules(model, name), f"{model}.{name}", "method",
                                         where, result) else None

    def xmlid(self, full, where, result):
        module = full.partition(".")[0]
        if module == refs.OFA_MODULE:
            key = full.partition(".")[2]
            if key in self.plan_keys:
                return "live"
            result.add(where, "UNRESOLVED_REF", full, "no upsert_record op of the plan defines this key")
            return None
        if self.live.xmlid(full):
            return "live"
        defined = self.index.xmlids.get(full)
        return "static" if self._static({defined} if defined else set(), full, "xmlid", where, result) else None

    def selection_value(self, model, name, value, where, result):
        live = self.live.fields(model).get(name)
        info = self.index.field_info(model, name)
        if (live and live["ttype"] != "selection") or (not live and (not info or info["type"] != "Selection")):
            return
        # Live values come from installed modules only; add what the plan's modules define (selection_add).
        values = (self.live.selection(model, name) if live else set()) | self.index.selection(model, name,
                                                                                              self.effective)
        if values and value not in values:
            result.add(where, "BAD_SELECTION", f"{model}.{name}",
                       f"{value!r} is not one of {', '.join(sorted(values))}")


def _domain_fields(domain):
    if not isinstance(domain, list):
        return []
    return [t[0] for t in domain if isinstance(t, list) and len(t) == 3 and isinstance(t[0], str)]


def _searches(value):
    """Every `{"$search": {...}}` spec inside a value."""
    if isinstance(value, dict):
        if set(value) == {"$search"} and isinstance(value["$search"], dict):
            yield value["$search"]
        for v in value.values():
            yield from _searches(v)
    elif isinstance(value, list):
        for v in value:
            yield from _searches(v)


def _is_ref(value):
    return isinstance(value, dict) and len(value) == 1 and next(iter(value)) in ("$ref", "$search", "$set", "$add")


def _count(status, result, prefix):
    if status is not None:
        setattr(result, f"{prefix}_checked", getattr(result, f"{prefix}_checked") + 1)
        if status == "static":
            setattr(result, f"{prefix}_static", getattr(result, f"{prefix}_static") + 1)


def lint_json(chk, plan, result):
    for op in planmod.operations(plan):
        where = f"plan.json: {op.get('id')}"
        typ = op.get("type")

        def count(status):
            _count(status, result, "json")
        if typ == "install_modules":
            for m in op.get("modules", []):
                if m not in chk.live.module_state:
                    chk._static({m} if m in chk.index.modules else set(), m, "module", where, result)
                    continue
                count("live")
                if chk.edition == "community" and chk.index.modules.get(m, {}).get("edition") == "enterprise":
                    result.add(where, "EDITION", m, "Enterprise module on a community target")
        elif typ == "set_settings":
            for k, v in (op.get("values") or {}).items():
                st = chk.field(SETTINGS, k, where, result)
                count(st)
                if st and isinstance(v, str):
                    chk.selection_value(SETTINGS, k, v, where, result)
        elif typ == "upsert_record":
            model = op.get("model")
            count(chk.model(model, where, result))
            for k, v in (op.get("values") or {}).items():
                st = chk.field(model, k, where, result)
                count(st)
                if st and isinstance(v, str) and not _is_ref(v):
                    chk.selection_value(model, k, v, where, result)
            for f in _domain_fields(op.get("match")):
                count(chk.path(model, f, where, result))
        elif typ == "call_method":
            model = op.get("model")
            count(chk.model(model, where, result))
            count(chk.method(model, op.get("method"), where, result))
            skip = op.get("skip_if") or {}
            if skip.get("model"):
                count(chk.model(skip["model"], where, result))
                for f in _domain_fields(skip.get("domain")):
                    count(chk.path(skip["model"], f, where, result))
        for spec in _searches(op):
            if spec.get("model"):
                count(chk.model(spec["model"], where, result))
                for f in _domain_fields(spec.get("domain")):
                    count(chk.path(spec["model"], f, where, result))
        for ref in planmod.ref_names(op):
            count(chk.xmlid(ref, where, result))


def _ignored(text):
    names = set()
    for block in IGNORE_RE.findall(text):
        names |= {n.strip().strip("`") for n in re.split(r"[,\s]+", block) if n.strip()}
    return names


def _check_dotted(chk, token, is_call, where, result):
    """One dotted name from the prose. Returns its status, or 'skip' when it is not an Odoo name."""
    segs = token.split(".")
    # Multi-segment model names first (`sale.order.line`), then `module.xmlid` (also `module.xmlid.field`),
    # then one-segment models: `base` is a model too, so `base.group_user` must be tried as an xmlid first.
    candidates = [k for k in range(len(segs), 1, -1)]
    xmlid = ".".join(segs[:2])
    if len(segs) >= 2 and (segs[0] in chk.live.module_state or segs[0] in chk.index.modules):
        multi = next((k for k in candidates if chk.has_model(".".join(segs[:k]))), None)
        if multi is None and (chk.live.xmlid(xmlid) or xmlid in chk.index.xmlids or len(segs) == 2):
            status = chk.xmlid(xmlid, where, result)
            model = chk.live.xmlid(xmlid)
            if status is None or len(segs) == 2 or not model:
                return status
            return chk.path(model, ".".join(segs[2:]), where, result)
    for k in candidates + [1]:
        model = ".".join(segs[:k])
        if not chk.has_model(model):
            continue
        if k == len(segs):
            return chk.model(model, where, result)
        name = segs[k]
        kind = chk.member(model, name)
        if kind is None:
            # A model prefix with an unknown member: `ir.model.access` (no such model, and ir.model has no
            # `access`) or `sale.order.require_payment`.
            result.add(where, "NOT_IN_20", token, f"no model {token!r}, and {model} has no field or method {name!r}"
                       if k == len(segs) - 1 else f"{model} has no field or method {name!r}")
            return None
        if kind[0] == "method":
            return chk.method(model, name, where, result)
        rest = ".".join(segs[k:])
        return chk.path(model, rest, where, result)
    return "skip"


def lint_md(chk, text, result):
    ignored = _ignored(text)
    fenced = FENCE_RE.findall(text)
    result.md_unchecked["fenced_blocks"] = sum(len(DOTTED_RE.findall(b)) + len(WORD_RE.findall(b)) for b in fenced)
    body = FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), IGNORE_RE.sub("", text))
    seen = {}
    for lineno, line in enumerate(body.splitlines(), 1):
        outside = SPAN_RE.sub(" ", line)
        result.md_unchecked["outside_backticks"] += sum(
            1 for t, _ in DOTTED_RE.findall(outside) if not _NOT_NAME_SUFFIX.search(t) and not t[0].isupper()
            and not re.search(r"https?://\S*" + re.escape(t), outside))
        for span in SPAN_RE.findall(line):
            if "/" in span or "@" in span:
                result.md_unchecked["path_spans"] += 1
                continue
            dotted = DOTTED_RE.findall(span)
            rest = DOTTED_RE.sub(" ", span)
            rest = re.sub(r"'[^']*'|\"[^\"]*\"", " ", rest)
            for w in WORD_RE.findall(rest):
                if w in _WORDS_IGNORED:
                    continue
                if not SNAKE_RE.match(w) or w in ignored or w in chk.own_names or w.startswith("x_"):
                    kind = "ignored" if w in ignored else "own_names" if w in chk.own_names else (
                        "custom_fields" if w.startswith("x_") else "bare_names")
                    result.md_unchecked[kind] += 1
                    continue
                if w in seen:
                    continue
                seen[w] = True
                if w in chk.index.known_names() or any(w in chk.live.fields(m) for m in chk.live._fields):
                    _count("live", result, "md")
                else:
                    result.add(f"plan.md:{lineno}", "NOT_IN_20", w,
                               "no field, method, module, xmlid or selection value of that name in Odoo 20.0")
            for token, call in dotted:
                if token in ignored:
                    result.md_unchecked["ignored"] += 1
                    continue
                if token in seen:
                    continue
                st = _check_dotted(chk, token, bool(call), f"plan.md:{lineno}", result)
                seen[token] = st
                if st == "skip":
                    result.md_unchecked["not_identifiers"] += 1
                else:
                    _count(st, result, "md")
    return result


def own_names(plan, target, extra=()):
    names = {target.name, target.db, "ofa_bot", "ofa_demo", refs.OFA_MODULE}
    # Structural keys only: field names inside `values` or domains are Odoo names and stay checked.
    names |= set(plan) | {k for op in planmod.operations(plan) for k in op} | set(planmod.upsert_keys(plan))
    names |= {op.get("id") for op in planmod.operations(plan) if op.get("id")}
    names |= {"plan_md_template", "plan_format", "scenario_format", "pre_state", "knowledge_refs", "depends_on",
              "skip_if", "min_count", "save_as", "res_ids", "duration_ms", "plan_sha256", "run_id", "db_uuid",
              "bot_groups", "lint_plan", "install_modules", "set_settings", "upsert_record", "call_method"}
    return names | set(extra)


def lint(client, index, plan, plan_md_text, edition, extra_names=()):
    live = Live(client)
    chk = Checker(live, index, plan, edition)
    chk.add_own_names(own_names(plan, client.target, extra_names))
    result = Result()
    lint_json(chk, plan, result)
    if plan_md_text is not None:
        lint_md(chk, plan_md_text, result)
    return result
