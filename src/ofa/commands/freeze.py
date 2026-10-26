"""ofa freeze: validate a plan offline and record its approved hash in plan.approved."""
import sys

from ofa import plan as planmod


def register(subparsers):
    p = subparsers.add_parser("freeze", help="approve a reviewed plan: write plan.approved with its sha256")
    p.add_argument("plan_dir", help="directory holding plan.json and plan.md")
    p.set_defaults(func=handler)


def handler(args):
    plan = planmod.load(args.plan_dir)
    problems = planmod.validate(args.plan_dir, plan)
    if problems:
        planmod.raise_problems(problems, sys.stderr)
    approved = planmod.freeze(args.plan_dir, plan)
    print(f"frozen: sha256 {approved['sha256']} at {approved['approved_at']}")
    return 0
