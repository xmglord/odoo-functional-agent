"""Knowledge entries (C11): restricted front matter parser, section check, discovery.

The front matter is a restricted YAML subset so that the stdlib can parse it:
one `key: value` per line, flow lists `[a, b]` only, no nesting.
"""
import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path

INDEX_NAME = "INDEX.md"
FENCE = "---"
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
AREA_RE = re.compile(r"^[a-z0-9_]+$")
AREA_INDEX_LINK_RE = re.compile(r"\]\(([a-z0-9_]+)/INDEX\.md\)")

REQUIRED_KEYS = ("title", "area", "odoo_version", "edition", "source", "verified_on", "verified_against")
LIST_KEYS = ("source", "verified_against", "modules", "models", "settings")
EDITIONS = ("community", "enterprise")
VERIFIED_AGAINST = ("source", "docs", "live")
REQUIRED_SECTIONS = ("When to use", "Configuration", "How to verify", "Pitfalls", "Alternatives")


class FrontMatterError(ValueError):
    pass


@dataclass
class Entry:
    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""
    error: str = None

    @property
    def verified_on(self):
        try:
            return parse_date(self.meta.get("verified_on", ""))
        except ValueError:
            return None


def parse_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise ValueError(f"not a YYYY-MM-DD date: {value!r}")
    return datetime.date.fromisoformat(value)


def _parse_value(raw, lineno):
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise FrontMatterError(f"line {lineno}: unterminated flow list")
        inner = raw[1:-1].strip()
        if "[" in inner or "{" in inner:
            raise FrontMatterError(f"line {lineno}: nested lists or maps are not allowed")
        return [item.strip() for item in inner.split(",") if item.strip()] if inner else []
    if raw.startswith("{"):
        raise FrontMatterError(f"line {lineno}: maps are not allowed")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def parse_front_matter(text):
    """Return (meta, body). Raise FrontMatterError when the block is missing or outside the subset."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        raise FrontMatterError("missing front matter (first line must be ---)")
    meta = {}
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == FENCE:
            return meta, "\n".join(lines[i:])
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            raise FrontMatterError(f"line {i}: indented line; nesting is not allowed")
        key, sep, raw = line.partition(":")
        key = key.strip()
        if not sep or not KEY_RE.match(key):
            raise FrontMatterError(f"line {i}: expected `key: value`")
        raw = raw.strip()
        if not raw:
            raise FrontMatterError(f"line {i}: empty value for {key!r} (nested maps are not allowed)")
        if key in meta:
            raise FrontMatterError(f"line {i}: duplicate key {key!r}")
        meta[key] = _parse_value(raw, i)
    raise FrontMatterError("unterminated front matter (no closing ---)")


def section_headings(body):
    """Level-2 headings of the body, skipping fenced code blocks."""
    headings, in_code = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code and line.startswith("## "):
            headings.append(line[3:].strip())
    return headings


def check_sections(body):
    """Problems with the required sections: missing ones, or present out of order."""
    headings = section_headings(body)
    missing = [s for s in REQUIRED_SECTIONS if s not in headings]
    problems = [f"missing section: ## {s}" for s in missing]
    present = [h for h in headings if h in REQUIRED_SECTIONS]
    if not missing and tuple(present) != REQUIRED_SECTIONS:
        problems.append("required sections out of order or repeated; expected: " + ", ".join(REQUIRED_SECTIONS))
    return problems


def check_meta(meta, version=None, area=None):
    problems = [f"missing key: {k}" for k in REQUIRED_KEYS if k not in meta]
    for k in LIST_KEYS:
        if k in meta and not isinstance(meta[k], list):
            problems.append(f"{k} must be a flow list [a, b]")
    for k in REQUIRED_KEYS:
        if k in meta and k not in LIST_KEYS and isinstance(meta[k], list):
            problems.append(f"{k} must be a scalar")
    if "verified_on" in meta:
        try:
            parse_date(meta["verified_on"])
        except ValueError as e:
            problems.append(f"verified_on: {e}")
    if meta.get("edition") not in (None, *EDITIONS):
        problems.append(f"edition must be one of {', '.join(EDITIONS)}")
    if isinstance(meta.get("source"), list) and not meta["source"]:
        problems.append("source must cite at least one doc URL or source path")
    va = meta.get("verified_against")
    if isinstance(va, list):
        if not va:
            problems.append("verified_against must not be empty")
        bad = [v for v in va if v not in VERIFIED_AGAINST]
        if bad:
            problems.append(f"verified_against: unknown {', '.join(bad)} (allowed: {', '.join(VERIFIED_AGAINST)})")
    if version is not None and "odoo_version" in meta and meta["odoo_version"] != version:
        problems.append(f"odoo_version {meta['odoo_version']} does not match folder {version}")
    if area is not None and "area" in meta and meta["area"] != area:
        problems.append(f"area {meta['area']} does not match folder {area}")
    return problems


def load_entry(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return Entry(Path(path), error=f"cannot read: {type(e).__name__}")
    try:
        meta, body = parse_front_matter(text)
    except FrontMatterError as e:
        return Entry(Path(path), body=text, error=str(e))
    return Entry(Path(path), meta, body)


def lint_entry(entry, version=None, area=None):
    if entry.error:
        return [entry.error]
    return check_meta(entry.meta, version, area) + check_sections(entry.body)


def area_dirs(version_dir):
    return sorted(p for p in Path(version_dir).iterdir() if p.is_dir() and not p.name.startswith("."))


def entry_paths(area_dir):
    """Topic files of one area: every *.md directly in it except INDEX.md."""
    return sorted(p for p in Path(area_dir).glob("*.md") if p.is_file() and p.name != INDEX_NAME)


def linked_area_indexes(index_text):
    """Area names linked as `<area>/INDEX.md` from a version INDEX.md, in order, without repeats."""
    return list(dict.fromkeys(AREA_INDEX_LINK_RE.findall(index_text)))
