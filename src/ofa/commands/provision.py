"""ofa provision <name>: create ofa_demo_<name> from the template, with bot user, key and marker."""
from ofa import provision


def register(subparsers):
    p = subparsers.add_parser("provision", help="create a fresh demo database ofa_demo_<name>")
    p.add_argument("name")
    p.set_defaults(func=handler)


def handler(args):
    return provision.provision(args.name)
