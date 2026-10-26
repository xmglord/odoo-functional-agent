"""ofa dump: canonical JSON of what a plan configured on a target (C10, used for R7)."""
import sys
from pathlib import Path

from ofa import client, dump


def register(subparsers):
    p = subparsers.add_parser("dump", help="canonical, id-free JSON of the state a plan configured on a target")
    p.add_argument("plan_dir")
    p.add_argument("--target", required=True)
    p.add_argument("--out", metavar="FILE", help="write here instead of stdout")
    p.set_defaults(func=handler)


def handler(args):
    plan = dump.load_plan(args.plan_dir)
    c = client.open_client(args.target)
    text = dump.canonical(dump.dump(c, plan))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0
