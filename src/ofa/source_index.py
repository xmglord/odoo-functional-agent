"""Static index of the Odoo source the demo server runs: modules, models, fields, methods, xmlids.

`ofa lint-plan` uses it for identifiers the live database cannot confirm yet, because the module that
defines them is not installed. The index is derived from Enterprise code as well as Community, so it is
built locally on demand and cached outside the repository (`~/.cache/ofa/`, or `$OFA_CACHE_DIR`); it is
never committed. `index_path` refuses a cache location inside the repository.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from ofa import ROOT
from ofa import config as configmod
from ofa.errors import EnvError, UsageError

FORMAT = "ofa.source_index/1"
FIELD_TYPES = {
    "Boolean", "Integer", "Float", "Monetary", "Char", "Text", "Html", "Date", "Datetime", "Binary", "Image",
    "Selection", "Many2one", "One2many", "Many2many", "Many2oneReference", "Reference", "Json", "Properties",
    "PropertiesDefinition", "Id",
}
RELATIONAL = {"Many2one", "One2many", "Many2many"}
_SKIP_DIRS = {"tests", "static", "migrations", "upgrades", "i18n", "__pycache__"}
_OPTIONS_RE = re.compile(r"""options=["']\{(.*?)\}["']""", re.S)
_OPTION_KEY_RE = re.compile(r"""['"](\w+)['"]\s*:""")
_WIDGET_RE = re.compile(r"""widget=["'](\w+)["']""")
_XMLID_RE = re.compile(r"<(?:record|menuitem|template|act_window|report|function)\b[^>]*?\bid=\"([^\"]+)\"", re.S)
# BaseModel and the ORM classes every model inherits from.
_ORM_FILES = ("orm/models.py", "orm/models_transient.py")


def cache_dir():
    return Path(os.environ.get("OFA_CACHE_DIR") or "~/.cache/ofa").expanduser()


def addons_roots(server):
    """The addons directories the server loads, in order, plus the base addons of the checkout."""
    opts = configmod._odoo_options(str(server.odoo_conf))
    roots = [Path(p.strip()).expanduser() for p in opts.get("addons_path", "").split(",") if p.strip()]
    odoo_pkg = Path(str(server.odoo_bin)).expanduser().parent / "odoo"
    roots.append(odoo_pkg / "addons")
    return [r for r in roots if r.is_dir()], odoo_pkg


def _fingerprint(roots):
    # The builder's own code is part of the key, so a parser change never reuses an old index.
    parts = [hashlib.sha256(Path(__file__).read_bytes()).hexdigest()]
    for root in roots:
        try:
            head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                                  timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            head = ""
        if not head:
            head = str(max((p.stat().st_mtime for p in root.glob("*/__manifest__.py")), default=0))
        parts.append(f"{root}={head}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def index_path(roots):
    path = cache_dir() / f"source_index_{_fingerprint(roots)}.json"
    resolved = path.resolve()
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents:
        raise UsageError(f"the source index must live outside the repository (it is derived from Enterprise "
                         f"code); set OFA_CACHE_DIR elsewhere, not {path}")
    return path


def _const(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _field_call(node):
    """`fields.X(...)` or `X(...)` with X a field type: (type, call) or None."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    return (name, node) if name in FIELD_TYPES else None


def _selection_values(call):
    values = []
    for node in list(call.args[:1]) + [k.value for k in call.keywords if k.arg in ("selection", "selection_add")]:
        lit = _const(node)
        if isinstance(lit, (list, tuple)):
            values += [v[0] for v in lit if isinstance(v, (list, tuple)) and v and isinstance(v[0], str)]
    return sorted(set(values)) or None


def _comodel(ftype, call):
    if ftype not in RELATIONAL:
        return None
    for k in call.keywords:
        if k.arg == "comodel_name":
            return _const(k.value)
    if call.args and isinstance(_const(call.args[0]), str):
        return _const(call.args[0])
    return None


def _parse_class(cls):
    attrs, fields, methods = {}, {}, []
    for stmt in cls.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(stmt.name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for t in targets:
                if not isinstance(t, ast.Name) or stmt.value is None:
                    continue
                if t.id in ("_name", "_inherit", "_inherits"):
                    attrs[t.id] = _const(stmt.value)
                    continue
                fc = _field_call(stmt.value)
                if fc:
                    ftype, call = fc
                    fields[t.id] = {"type": ftype, "comodel": _comodel(ftype, call),
                                    "selection": _selection_values(call) if ftype == "Selection" else None}
    inherit = attrs.get("_inherit")
    inherit = [inherit] if isinstance(inherit, str) else [i for i in (inherit or []) if isinstance(i, str)]
    name = attrs.get("_name") if isinstance(attrs.get("_name"), str) else (inherit[0] if inherit else None)
    if not name:
        return None
    inherits = attrs.get("_inherits") if isinstance(attrs.get("_inherits"), dict) else {}
    parents = [i for i in inherit if i != name] + [k for k in inherits if isinstance(k, str)]
    return name, {"fields": fields, "methods": methods, "parents": parents}


def _py_files(module_dir):
    for dirpath, dirnames, filenames in os.walk(module_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for f in filenames:
            if f.endswith(".py"):
                yield Path(dirpath) / f


def _xml_files(module_dir):
    for dirpath, dirnames, filenames in os.walk(module_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for f in filenames:
            if f.endswith(".xml"):
                yield Path(dirpath) / f


def _classes(path, choices):
    """Model classes of a file; also collects `(key, label)` string pairs, the shape of selection choices
    built in functions (`selection=_get_policies`), into `choices`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            parsed = _parse_class(node)
            if parsed:
                yield parsed
        elif (isinstance(node, ast.Tuple) and len(node.elts) == 2 and isinstance(node.elts[0], ast.Constant)
              and isinstance(node.elts[0].value, str)):
            choices.add(node.elts[0].value)


def build(roots, odoo_pkg):
    modules, models, xmlids = {}, {}, {}
    choices, view_options = set(), set()
    seen = set()
    for root in roots:
        for mdir in sorted(p for p in root.iterdir() if p.is_dir()):
            manifest = mdir / "__manifest__.py"
            if mdir.name in seen or not manifest.is_file():
                continue
            seen.add(mdir.name)
            data = _const(ast.parse(manifest.read_text(encoding="utf-8", errors="replace")).body[0].value) or {}
            license_ = str(data.get("license", "LGPL-3"))
            modules[mdir.name] = {"depends": list(data.get("depends", [])),
                                  "auto_install": data.get("auto_install", False),
                                  "edition": "enterprise" if license_.startswith("OEEL") else "community"}
            for py in _py_files(mdir):
                for name, cdef in _classes(py, choices):
                    models.setdefault(name, []).append({"module": mdir.name, **cdef})
            for xml in _xml_files(mdir):
                text = xml.read_text(encoding="utf-8", errors="replace")
                view_options.update(_WIDGET_RE.findall(text))
                for opts in _OPTIONS_RE.findall(text):
                    view_options.update(_OPTION_KEY_RE.findall(opts))
                for xid in _XMLID_RE.findall(text):
                    full = xid if "." in xid else f"{mdir.name}.{xid}"
                    xmlids.setdefault(full, mdir.name)
    base_methods = set()
    for rel in _ORM_FILES:
        path = odoo_pkg / rel
        if path.is_file():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    base_methods |= {s.name for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {"format": FORMAT, "roots": [str(r) for r in roots], "modules": modules, "models": models,
            "xmlids": xmlids, "base_methods": sorted(base_methods), "choices": sorted(choices),
            "view_options": sorted(view_options)}


class SourceIndex:
    def __init__(self, data):
        self.data = data
        self.modules = data["modules"]
        self.models = data["models"]
        self.xmlids = data["xmlids"]
        self.base_methods = set(data["base_methods"])
        self._memo = {}

    @classmethod
    def load(cls, server=None, *, rebuild=False):
        server = server or configmod.load().server
        roots, odoo_pkg = addons_roots(server)
        if not roots:
            raise EnvError("SOURCE_MISSING", "no addons directory found from the Odoo conf's addons_path")
        path = index_path(roots)
        if path.is_file() and not rebuild:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("format") == FORMAT:
                    return cls(data)
            except ValueError:
                pass
        data = build(roots, odoo_pkg)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
        return cls(data)

    def deps(self, names):
        """`names` plus everything they depend on."""
        out, todo = set(), list(names)
        while todo:
            m = todo.pop()
            if m in out or m not in self.modules:
                continue
            out.add(m)
            todo += self.modules[m]["depends"]
        return out

    def closure(self, names):
        """`names`, their dependencies, and the auto_install modules that follow (Odoo's install rule)."""
        out = self.deps(names)
        changed = True
        while changed:
            changed = False
            for m, info in self.modules.items():
                auto = info["auto_install"]
                if m in out or not auto:
                    continue
                trigger = auto if isinstance(auto, list) else info["depends"]
                if all(d in out for d in trigger):
                    out |= self.deps([m])
                    changed = True
        return out

    def _depends_on(self, a, b):
        key = ("deps", a)
        if key not in self._memo:
            self._memo[key] = self.deps([a])
        return b in self._memo[key]

    def model_modules(self, model):
        return {d["module"] for d in self.models.get(model, [])}

    def _member_modules(self, model, kind, name, stack=()):
        key = (model, kind, name)
        if key in self._memo:
            return self._memo[key]
        if model in stack:
            return set()
        out = set()
        for d in self.models.get(model, []):
            if name in d[kind]:
                out.add(d["module"])
            for parent in d["parents"]:
                # Through inheritance the member needs both this def's module and the parent's
                # defining module; keep whichever of the two brings the other along.
                for pm in self._member_modules(parent, kind, name, stack + (model,)):
                    out.add(pm if self._depends_on(pm, d["module"]) else d["module"])
        self._memo[key] = out
        return out

    def field_modules(self, model, field):
        return self._member_modules(model, "fields", field)

    def method_modules(self, model, method):
        if method in self.base_methods and self.models.get(model):
            return {"base"}
        return self._member_modules(model, "methods", method)

    def field_info(self, model, field, stack=()):
        if model in stack:
            return None
        for d in self.models.get(model, []):
            if field in d["fields"]:
                return d["fields"][field]
        for d in self.models.get(model, []):
            for parent in d["parents"]:
                info = self.field_info(parent, field, stack + (model,))
                if info:
                    return info
        return None

    def selection(self, model, field, modules=None, stack=()):
        """Selection values of a field from the source, optionally only those `modules` define or add."""
        if model in stack:
            return set()
        values = set()
        for d in self.models.get(model, []):
            info = d["fields"].get(field)
            if info and info.get("selection") and (modules is None or d["module"] in modules):
                values |= set(info["selection"])
            for parent in d["parents"]:
                values |= self.selection(parent, field, modules, stack + (model,))
        return values

    def known_names(self):
        """Every bare name the source defines: fields, methods, modules, xmlid names, selection choices and
        view widget names and options."""
        if "names" not in self._memo:
            names = (set(self.modules) | self.base_methods | {x.partition(".")[2] for x in self.xmlids}
                     | set(self.data["choices"]) | set(self.data["view_options"]))
            for defs in self.models.values():
                for d in defs:
                    names |= set(d["fields"]) | set(d["methods"])
                    for info in d["fields"].values():
                        names |= set(info.get("selection") or [])
            self._memo["names"] = names
        return self._memo["names"]
