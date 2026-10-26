"""CLI dispatcher: loads each command module and maps OfaError to exit codes."""
import argparse
import importlib
import sys

from ofa.errors import ENVIRONMENT, USAGE, OfaError

COMMANDS = (
    "targets", "doctor", "inspect", "server", "template", "provision", "reset", "drop",
    "validate", "freeze", "apply", "test", "dump", "stale", "lint_plan",
)


class CommandLoadError(Exception):
    def __init__(self, name, exc):
        super().__init__(f"cannot load command {name}: {type(exc).__name__}")


def cli_name(module_name):
    return module_name.replace("_", "-")


def _register_stub(subparsers, name):
    parser = subparsers.add_parser(name, help="not implemented")
    parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    def handler(args):
        print(f"ofa: {USAGE}: {name}: not implemented", file=sys.stderr)
        return USAGE

    parser.set_defaults(func=handler)


def build_parser(commands=COMMANDS, package="ofa.commands"):
    parser = argparse.ArgumentParser(prog="ofa", description="Plan, apply and test Odoo functional configuration on demo databases.")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    for name in commands:
        full = f"{package}.{name}"
        try:
            module = importlib.import_module(full)
        except ModuleNotFoundError as e:
            # Only the command module itself being absent means "not implemented";
            # a missing dependency inside it is a broken command.
            if e.name != full:
                raise CommandLoadError(name, e) from e
            _register_stub(subparsers, cli_name(name))
            continue
        except Exception as e:
            raise CommandLoadError(name, e) from e
        module.register(subparsers)
    return parser


def main(argv=None, commands=COMMANDS, package="ofa.commands"):
    try:
        parser = build_parser(commands, package)
    except CommandLoadError as e:
        print(f"ofa: {ENVIRONMENT}: {e}", file=sys.stderr)
        return ENVIRONMENT
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return USAGE
    try:
        return args.func(args)
    except OfaError as e:
        print(f"ofa: {e.label}: {e.msg}", file=sys.stderr)
        return e.exit_code
