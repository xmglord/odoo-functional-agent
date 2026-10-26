"""`ofa stale`: list knowledge entries verified before a date, or lint them (C11)."""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import ofa
from ofa import knowledge
from ofa.errors import OfaError, UsageError, ValidationError


def register(subparsers):
    p = subparsers.add_parser(
        "stale",
        help="list knowledge entries verified before a date, or lint them",
        description="Without --lint, print entries whose verified_on is before --since (one path per line). "
                    "With --lint, check front matter and required sections; --since is not used.",
    )
    p.add_argument("--since", help="YYYY-MM-DD; default: committer date of HEAD in the Odoo checkout (from config)")
    p.add_argument("--version", default=ofa.ODOO_SERIES, help="knowledge version folder (default %(default)s)")
    p.add_argument("--area", help="restrict every check to <root>/<version>/<area>/")
    p.add_argument("--root", help="directory that contains <version>/ (default: <plugin>/knowledge)")
    p.add_argument("--lint", action="store_true", help="validate entries instead of listing stale ones")
    p.set_defaults(func=handler)


def default_since():
    """Committer date of HEAD in the Odoo checkout named by server.odoo_bin (C2)."""
    try:
        # Lazy and through sys.modules: config belongs to another module (M1) and may be absent.
        config = importlib.import_module("ofa.config")
        odoo_bin = config.load().server.odoo_bin
    except (ImportError, OfaError, OSError, AttributeError, ValueError) as e:
        raise UsageError(f"--since is required: cannot load the ofa config ({type(e).__name__}: {e})") from e
    checkout = os.path.dirname(os.path.expanduser(str(odoo_bin)))
    try:
        out = subprocess.run(["git", "-C", checkout, "log", "-1", "--format=%cs"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise UsageError(f"--since is required: cannot read the Odoo checkout date ({type(e).__name__})") from e
    if out.returncode != 0 or not out.stdout.strip():
        raise UsageError(f"--since is required: git log failed in {checkout}")
    return out.stdout.strip()


def _parse_since(value):
    try:
        return knowledge.parse_date(value)
    except ValueError as e:
        raise UsageError(f"--since: {e}") from e


def _scope(args):
    root = Path(args.root) if args.root else ofa.ROOT / "knowledge"
    version_dir = root / args.version
    if not version_dir.is_dir():
        raise ValidationError("NO_VERSION", f"knowledge version folder not found: {version_dir}")
    if args.area is None:
        return version_dir, knowledge.area_dirs(version_dir)
    if not knowledge.AREA_RE.match(args.area):
        raise UsageError(f"--area: invalid area name {args.area!r}")
    area_dir = version_dir / args.area
    if not area_dir.is_dir():
        raise ValidationError("NO_AREA", f"area folder not found: {area_dir}")
    if not (area_dir / knowledge.INDEX_NAME).is_file():
        raise ValidationError("NO_AREA_INDEX", f"area index not found: {area_dir / knowledge.INDEX_NAME}")
    return version_dir, [area_dir]


def _lint(args, version_dir, areas):
    problems = []
    if args.area is None:
        top = version_dir / knowledge.INDEX_NAME
        if not top.is_file():
            problems.append((top, "missing version index"))
        else:
            for name in knowledge.linked_area_indexes(top.read_text(encoding="utf-8")):
                target = version_dir / name / knowledge.INDEX_NAME
                if not target.is_file():
                    print(f"WARN missing area index: {target}", file=sys.stderr)
        for area_dir in areas:
            if not (area_dir / knowledge.INDEX_NAME).is_file():
                problems.append((area_dir / knowledge.INDEX_NAME, "missing area index"))
    count = 0
    for area_dir in areas:
        for path in knowledge.entry_paths(area_dir):
            count += 1
            entry = knowledge.load_entry(path)
            for msg in knowledge.lint_entry(entry, args.version, area_dir.name):
                problems.append((path, msg))
    for path, msg in problems:
        print(f"ERROR {path}: {msg}", file=sys.stderr)
    if problems:
        files = len({p for p, _ in problems})
        raise ValidationError("KNOWLEDGE_LINT", f"{len(problems)} problem(s) in {files} file(s)")
    print(f"ok: {count} entr{'y' if count == 1 else 'ies'} checked")
    return 0


def handler(args):
    version_dir, areas = _scope(args)
    if args.lint:
        return _lint(args, version_dir, areas)
    since = _parse_since(args.since if args.since else default_since())
    for area_dir in areas:
        for path in knowledge.entry_paths(area_dir):
            entry = knowledge.load_entry(path)
            verified = entry.verified_on
            # An entry without a readable verified_on is never known to be current.
            if verified is None or verified < since:
                print(path)
    return 0
