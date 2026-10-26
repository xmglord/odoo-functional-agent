"""ofa drop <name>...: drop registered demo databases whose marker matches."""
from ofa import provision


def register(subparsers):
    p = subparsers.add_parser("drop", help="drop one or more registered demo databases")
    p.add_argument("names", nargs="+")
    p.set_defaults(func=handler)


def handler(args):
    return provision.drop(args.names)
