"""ofa validate: check a plan dir against the ofa.plan/1 rules (offline unless --target)."""
import sys

from ofa import client, config, guard
from ofa import plan as planmod


def register(subparsers):
    p = subparsers.add_parser("validate", help="check a plan dir against the ofa.plan/1 rules")
    p.add_argument("plan_dir", help="directory holding plan.json and plan.md")
    p.add_argument("--target", help="also check the target's edition and that every $ref resolves on it (read-only)")
    p.set_defaults(func=handler)


def handler(args):
    plan = planmod.load(args.plan_dir)
    edition = None
    if args.target:
        target = config.load().target(args.target)
        guard.check_static(target)
        edition = target.edition
    problems = planmod.validate(args.plan_dir, plan, target_edition=edition)
    if not problems and args.target:
        problems = planmod.check_online(client.open_client(args.target), plan)
    if problems:
        planmod.raise_problems(problems, sys.stderr)
    ordered = [op["id"] for op in planmod.order(plan)]
    print(f"ok: {len(ordered)} operations, sha256 {planmod.plan_hash(plan)}")
    for oid in ordered:
        print(f"  {oid}")
    return 0
