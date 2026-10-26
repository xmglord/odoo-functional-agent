"""Plan format `ofa.plan/1`: loading, validation, execution order and freeze hash (C6)."""
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import ofa
from ofa import refs
from ofa.errors import UsageError, ValidationError

FORMAT = "ofa.plan/1"
OP_TYPES = ("install_modules", "set_settings", "upsert_record", "call_method")
EDITIONS = ("community", "enterprise")
ID_RE = re.compile(r"^op_[a-z0-9_]+$")
KEY_RE = re.compile(r"^[a-z0-9_]{1,60}$")
APPROVED_FILE = "plan.approved"

# Every code validate() can report. Each one has a failing fixture under
# tests/fixtures/plans/invalid_<code lowercased>/.
RULE_CODES = (
    "BAD_FORMAT",             # header: format, odoo_version, edition, operations
    "BAD_OP",                 # op shape: unknown type, missing or mistyped field
    "BAD_ID",                 # id does not match ^op_[a-z0-9_]+$
    "DUPLICATE_ID",
    "UNKNOWN_DEPENDENCY",     # depends_on names no op of the plan
    "CYCLE",
    "EMPTY_RATIONALE",
    "MISSING_KNOWLEDGE_REF",  # path not under the repo root
    "OP_NOT_IN_PLAN_MD",      # R6: every op id appears as [op_id] in plan.md
    "BAD_KEY",                # upsert key does not match ^[a-z0-9_]{1,60}$
    "CREATE_NOT_ALLOWED",     # $create anywhere in a plan
    "SKIP_IF_REQUIRED",       # call_method without skip_if
    "EDITION_MISMATCH",       # enterprise op or plan on a community target
)
# Only with a live target (check_online): a $ref that does not resolve.
ONLINE_CODES = ("UNRESOLVED_REF",)

_REQUIRED = {
    "install_modules": {"modules": list},
    "set_settings": {"values": dict},
    "upsert_record": {"model": str, "key": str, "values": dict},
    "call_method": {"model": str, "target": dict, "method": str},
}
_OPTIONAL = {
    "upsert_record": {"match": list},
    "call_method": {"params": dict, "skip_if": dict, "wizards": dict},
}


@dataclass(frozen=True)
class Problem:
    code: str
    op_id: str | None
    message: str

    def __str__(self):
        where = f"[{self.op_id}] " if self.op_id else ""
        return f"{self.code}: {where}{self.message}"


def load(plan_dir):
    path = Path(plan_dir) / "plan.json"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise UsageError(f"{path} not found") from None
    except OSError as e:
        raise UsageError(f"cannot read {path}: {e.strerror}") from None
    try:
        plan = json.loads(text)
    except ValueError as e:
        raise ValidationError("BAD_JSON", f"{path} is not valid JSON ({e})") from None
    if not isinstance(plan, dict):
        raise ValidationError("BAD_FORMAT", f"{path} must hold a JSON object")
    return plan


def canonical_bytes(plan):
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def plan_hash(plan):
    return hashlib.sha256(canonical_bytes(plan)).hexdigest()


def operations(plan):
    ops = plan.get("operations")
    return [op for op in ops if isinstance(op, dict)] if isinstance(ops, list) else []


def _walk(value):
    """Yield every dict and list nested in value, value included."""
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            yield v
            stack.extend(v.values())
        elif isinstance(v, list):
            yield v
            stack.extend(v)


def ref_names(value):
    """Every `$ref` string used anywhere in value."""
    return [d["$ref"] for d in _walk(value) if isinstance(d, dict) and len(d) == 1 and isinstance(d.get("$ref"), str)]


def _is_ref(value):
    return isinstance(value, dict) and len(value) == 1 and next(iter(value)) in ("$ref", "$search")


def _check_header(plan, problems):
    if plan.get("format") != FORMAT:
        problems.append(Problem("BAD_FORMAT", None, f"format must be {FORMAT!r}"))
    if plan.get("odoo_version") != ofa.ODOO_SERIES:
        problems.append(Problem("BAD_FORMAT", None, f"odoo_version must be {ofa.ODOO_SERIES!r}"))
    if plan.get("edition") not in EDITIONS:
        problems.append(Problem("BAD_FORMAT", None, f"edition must be one of {', '.join(EDITIONS)}"))
    if not isinstance(plan.get("title"), str) or not plan["title"].strip():
        problems.append(Problem("BAD_FORMAT", None, "title must be a non-empty string"))
    ops = plan.get("operations")
    if not isinstance(ops, list) or not ops:
        problems.append(Problem("BAD_FORMAT", None, "operations must be a non-empty list"))
    elif any(not isinstance(op, dict) for op in ops):
        problems.append(Problem("BAD_FORMAT", None, "every operation must be an object"))


def _check_op_shape(op, oid, problems):
    t = op.get("type")
    if t not in OP_TYPES:
        problems.append(Problem("BAD_OP", oid, f"type must be one of {', '.join(OP_TYPES)}"))
        return
    for name, kind in _REQUIRED[t].items():
        if not isinstance(op.get(name), kind):
            problems.append(Problem("BAD_OP", oid, f"{t} needs {name} ({kind.__name__})"))
    for name, kind in _OPTIONAL.get(t, {}).items():
        if op.get(name) is not None and not isinstance(op[name], kind):
            problems.append(Problem("BAD_OP", oid, f"{name} must be a {kind.__name__}"))
    if t == "install_modules" and isinstance(op.get("modules"), list):
        if not op["modules"] or not all(isinstance(m, str) and m for m in op["modules"]):
            problems.append(Problem("BAD_OP", oid, "modules must be a non-empty list of module names"))
    if t in ("set_settings", "upsert_record") and isinstance(op.get("values"), dict) and not op["values"]:
        problems.append(Problem("BAD_OP", oid, "values must not be empty"))
    if t == "call_method":
        if isinstance(op.get("target"), dict) and not _is_ref(op["target"]):
            problems.append(Problem("BAD_OP", oid, "target must be a {\"$ref\"} or {\"$search\"}"))
        if isinstance(op.get("method"), str) and op["method"].startswith("_"):
            problems.append(Problem("BAD_OP", oid, "private methods are not callable over JSON-2"))
        skip = op.get("skip_if")
        if isinstance(skip, dict):
            if not isinstance(skip.get("model"), str) or not isinstance(skip.get("domain"), list):
                problems.append(Problem("BAD_OP", oid, "skip_if needs model (str) and domain (list)"))
            mc = skip.get("min_count", 1)
            if isinstance(mc, bool) or not isinstance(mc, int) or mc < 1:
                problems.append(Problem("BAD_OP", oid, "skip_if.min_count must be an integer >= 1"))
        wizards = op.get("wizards")
        if isinstance(wizards, dict) and not all(isinstance(k, str) and isinstance(v, str) for k, v in wizards.items()):
            problems.append(Problem("BAD_OP", oid, "wizards maps wizard model names to method names"))
    company = op.get("company")
    if company is not None and not _is_ref(company):
        problems.append(Problem("BAD_OP", oid, "company must be null or a {\"$ref\"}"))
    if op.get("edition", "community") not in EDITIONS:
        problems.append(Problem("BAD_OP", oid, f"edition must be one of {', '.join(EDITIONS)}"))
    if not isinstance(op.get("depends_on", []), list):
        problems.append(Problem("BAD_OP", oid, "depends_on must be a list of op ids"))
    if not isinstance(op.get("knowledge_refs", []), list):
        problems.append(Problem("BAD_OP", oid, "knowledge_refs must be a list of paths"))


def _check_knowledge_ref(ref, root):
    if not isinstance(ref, str) or not ref:
        return False
    rel = ref.split("#", 1)[0]
    if not rel or Path(rel).is_absolute():
        return False
    path = (root / rel).resolve()
    return path.is_relative_to(root.resolve()) and path.is_file()


def _deps(op):
    deps = op.get("depends_on")
    return deps if isinstance(deps, list) else []


def _unorderable(ops):
    """Ids left over by Kahn's algorithm: the ops on or behind a dependency cycle."""
    ids = {op["id"] for op in ops}
    left = {op["id"]: {d for d in _deps(op) if d in ids} for op in ops}
    progress = True
    while progress:
        progress = False
        for oid, deps in list(left.items()):
            if not deps & left.keys():
                del left[oid]
                progress = True
    return [op["id"] for op in ops if op["id"] in left]


def validate(plan_dir, plan=None, *, target_edition=None, root=None):
    """Return every offline problem of the plan (C6). Empty means valid."""
    plan_dir = Path(plan_dir)
    root = Path(root or ofa.ROOT)
    plan = load(plan_dir) if plan is None else plan
    problems = []
    _check_header(plan, problems)
    ops = operations(plan)
    try:
        plan_md = (plan_dir / "plan.md").read_text(encoding="utf-8")
    except OSError:
        plan_md = None
        problems.append(Problem("OP_NOT_IN_PLAN_MD", None, "plan.md is missing"))

    seen = set()
    graph_ops = []
    for i, op in enumerate(ops):
        oid = op.get("id")
        if not isinstance(oid, str) or not ID_RE.match(oid):
            problems.append(Problem("BAD_ID", oid if isinstance(oid, str) else None,
                                    f"operation #{i + 1}: id must match {ID_RE.pattern}"))
            continue
        if oid in seen:
            problems.append(Problem("DUPLICATE_ID", oid, "id is used by more than one operation"))
            continue
        seen.add(oid)
        graph_ops.append(op)

    for op in ops:
        oid = op.get("id") if isinstance(op.get("id"), str) else None
        _check_op_shape(op, oid, problems)
        for dep in _deps(op):
            if dep not in seen:
                problems.append(Problem("UNKNOWN_DEPENDENCY", oid, f"depends_on {dep!r} is not an op id of this plan"))
        if not isinstance(op.get("rationale"), str) or not op["rationale"].strip():
            problems.append(Problem("EMPTY_RATIONALE", oid, "rationale must be a non-empty line"))
        krefs = op.get("knowledge_refs")
        for ref in krefs if isinstance(krefs, list) else []:
            if not _check_knowledge_ref(ref, root):
                problems.append(Problem("MISSING_KNOWLEDGE_REF", oid, f"knowledge ref {ref!r} is not a file in the repo"))
        if plan_md is not None and oid and f"[{oid}]" not in plan_md:
            problems.append(Problem("OP_NOT_IN_PLAN_MD", oid, f"plan.md does not mention [{oid}]"))
        if op.get("type") == "upsert_record" and isinstance(op.get("key"), str) and not KEY_RE.match(op["key"]):
            problems.append(Problem("BAD_KEY", oid, f"key must match {KEY_RE.pattern}"))
        if any(isinstance(d, dict) and "$create" in d for d in _walk(op)):
            problems.append(Problem("CREATE_NOT_ALLOWED", oid, "$create is allowed in scenarios only; use an upsert_record op"))
        if op.get("type") == "call_method" and op.get("skip_if") is None:
            problems.append(Problem("SKIP_IF_REQUIRED", oid, "call_method needs skip_if so a re-apply reports unchanged"))
        if target_edition == "community" and op.get("edition") == "enterprise":
            problems.append(Problem("EDITION_MISMATCH", oid, "enterprise operation on a community target"))

    if target_edition == "community" and plan.get("edition") == "enterprise":
        problems.append(Problem("EDITION_MISMATCH", None, "enterprise plan on a community target"))

    stuck = _unorderable(graph_ops)
    if stuck:
        problems.append(Problem("CYCLE", stuck[0], "dependency cycle among " + ", ".join(stuck)))
    return problems


def order(plan):
    """Topological order of the operations; ties keep list order. Assumes a valid plan."""
    ops = operations(plan)
    pending = list(ops)
    done = set()
    result = []
    while pending:
        for i, op in enumerate(pending):
            if all(d in done for d in _deps(op)):
                result.append(pending.pop(i))
                done.add(op["id"])
                break
        else:
            raise ValidationError("CYCLE", "dependency cycle")
    return result


def upsert_keys(plan):
    return {op["key"] for op in operations(plan) if op.get("type") == "upsert_record" and isinstance(op.get("key"), str)}


def check_online(client, plan):
    """Problems only a live target shows: every `$ref` must resolve.

    An `__ofa__.<key>` ref is fine when an upsert op of this plan defines that key.
    """
    problems = []
    keys = upsert_keys(plan)
    cache = {}
    for op in operations(plan):
        for ref in ref_names(op):
            module, _, name = ref.partition(".")
            if module == refs.OFA_MODULE and name in keys:
                continue
            if ref not in cache:
                try:
                    refs.resolve(client, {"$ref": ref}, {})
                    cache[ref] = True
                except ValidationError:
                    cache[ref] = False
            if not cache[ref]:
                problems.append(Problem("UNRESOLVED_REF", op.get("id"), f"{ref} does not exist on the target"))
    return problems


def raise_problems(problems, out):
    """Print each problem to `out` and raise a ValidationError carrying the first code."""
    for p in problems:
        print(f"  {p}", file=out)
    raise ValidationError(problems[0].code, f"{len(problems)} problem(s) in the plan")


def freeze(plan_dir, plan=None, now=None):
    plan = load(plan_dir) if plan is None else plan
    approved = {"sha256": plan_hash(plan),
                "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))}
    path = Path(plan_dir) / APPROVED_FILE
    tmp = path.with_name(f".{APPROVED_FILE}.tmp")
    tmp.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return approved


def check_approved(plan_dir, plan):
    """Return the plan hash when plan.approved exists and matches; raise otherwise."""
    path = Path(plan_dir) / APPROVED_FILE
    try:
        approved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValidationError("NOT_APPROVED", f"{path} not found; review the plan and run ofa freeze") from None
    except (OSError, ValueError):
        raise ValidationError("NOT_APPROVED", f"{path} is unreadable; run ofa freeze again") from None
    sha = plan_hash(plan)
    if not isinstance(approved, dict) or approved.get("sha256") != sha:
        raise ValidationError("HASH_MISMATCH", "plan.json changed after it was frozen; review it and run ofa freeze again")
    return sha
