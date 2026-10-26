"""ofa template build: rebuild the template DB that demo DBs are copied from."""
from ofa import provision


def register(subparsers):
    p = subparsers.add_parser("template", help="build the template database")
    p.add_argument("action", choices=("build",))
    p.add_argument("name", nargs="?", help="template name (must equal server.template_db)")
    p.set_defaults(func=handler)


def handler(args):
    return provision.template_build(args.name)
