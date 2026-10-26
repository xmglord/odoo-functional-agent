"""ofa lint-plan: check the identifiers of plan.json and plan.md against the target and the 20.0 source."""
import json
import sys
from pathlib import Path

from ofa import ROOT, client, config, lint
from ofa import plan as planmod
from ofa.errors import USAGE
from ofa.source_index import SourceIndex


def register(subparsers):
    p = subparsers.add_parser("lint-plan", help="check every model, field, module and xmlid a plan names (read-only)")
    p.add_argument("plan_dir", help="directory holding plan.json and plan.md")
    p.add_argument("--target", required=True, help="demo target to check against, read-only")
    p.add_argument("--json", action="store_true", help="print the result as JSON instead of lines")
    p.add_argument("--rebuild-index", action="store_true", help="rebuild the local source index first")
    p.set_defaults(func=handler)


def _repo_names(plan_dir):
    """Scenario ids and knowledge entry names: ofa's own vocabulary that plan.md may quote."""
    names = set()
    for base in (ROOT / "scenarios", Path(plan_dir) / "scenarios"):
        names |= {p.stem for p in base.rglob("*.json")} if base.is_dir() else set()
    names |= {p.stem for p in (ROOT / "knowledge").rglob("*.md")}
    # The skill names the target after the plan's slug; any registered target may be quoted too.
    slug = Path(plan_dir).resolve().name
    names |= {slug, f"ofa_demo_{slug}"}
    for t in config.load().targets.values():
        names |= {t.name, t.db}
    return names


def handler(args):
    plan = planmod.load(args.plan_dir)
    md_path = Path(args.plan_dir) / "plan.md"
    md = md_path.read_text(encoding="utf-8") if md_path.is_file() else None
    c = client.open_client(args.target)
    index = SourceIndex.load(rebuild=args.rebuild_index)
    result = lint.lint(c, index, plan, md, c.target.edition, extra_names=_repo_names(args.plan_dir))
    if args.json:
        print(json.dumps({"problems": [{**p.__dict__, "severity": p.severity} for p in result.problems],
                          "plan_json": {"checked": result.json_checked, "static": result.json_static},
                          "plan_md": {"checked": result.md_checked, "static": result.md_static,
                                      "unchecked": result.md_unchecked}}, indent=2))
    else:
        for p in result.problems:
            print(p.line())
        u = result.md_unchecked
        print(f"plan.json: {result.json_checked} identifiers checked ({result.json_static} only in the source, "
              f"from modules the plan installs)")
        if md is None:
            print("plan.md: missing, prose not checked")
        else:
            print(f"plan.md: {result.md_checked} dotted names checked ({result.md_static} only in the source); "
                  f"not checked: {u['bare_names']} bare names, {u['path_spans']} path spans, "
                  f"{u['not_identifiers']} non-Odoo dotted names, {u['outside_backticks']} dotted names outside "
                  f"backticks, {u['fenced_blocks']} tokens in fenced blocks, {u['own_names']} plan/ofa names, "
                  f"{u['custom_fields']} custom x_ names, {u['ignored']} ignored")
        warnings = len(result.problems) - len(result.errors)
        print(f"{len(result.errors)} error(s), {warnings} warning(s)", file=sys.stderr)
    return USAGE if result.errors else 0
