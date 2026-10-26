"""ofa apply: apply a frozen plan to a demo target, idempotently (C7)."""
import sys

from ofa import client, executor
from ofa import plan as planmod
from ofa.errors import FUNCTIONAL_FAILURE, OK


def register(subparsers):
    p = subparsers.add_parser("apply", help="apply a frozen plan to a demo target; prints the run id")
    p.add_argument("plan_dir", help="directory holding plan.json and plan.approved")
    p.add_argument("--target", required=True)
    p.set_defaults(func=handler)


def handler(args):
    plan = planmod.load(args.plan_dir)
    sha = planmod.check_approved(args.plan_dir, plan)
    c = client.open_client(args.target)
    problems = planmod.validate(args.plan_dir, plan, target_edition=c.target.edition)
    if problems:
        planmod.raise_problems(problems, sys.stderr)
    record = executor.run(c, plan, args.plan_dir, sha)
    print(record["run_id"])
    from_run = executor.produced_in_run(plan, record)
    for op in record["ops"]:
        line = f"  {op['op_id']}: {op['status']}"
        if op["pre_state"]:
            line += " (pre_state: already true before this plan)"
        elif op["status"] == "unchanged" and op["op_id"] in from_run:
            line += " (state produced earlier in this run)"
        if op["error"]:
            line += f": {op['error']}"
        print(line, file=sys.stderr)
    return FUNCTIONAL_FAILURE if executor.has_failure(record) else OK
