"""ofa reset <name>: drop and provision again."""
from ofa import provision


def register(subparsers):
    p = subparsers.add_parser("reset", help="drop a demo database and provision it again")
    p.add_argument("name")
    p.set_defaults(func=handler)


def handler(args):
    return provision.reset(args.name)
