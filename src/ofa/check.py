"""ofa-check: read-only readiness report for the help skill.

It prints what `ofa doctor`, `ofa server status` and `ofa targets` print. It is a separate command word because
the guard hook activates on `ofa` in a command position, and asking for help is not using the agent. The hook has
no exception for it, so every session the hook guards today stays guarded. See "When it acts" in docs/guard.md.
"""
import contextlib
import sys

from ofa import cli

CHECKS = (("doctor",), ("server", "status"), ("targets",))


def main():
    with contextlib.redirect_stderr(sys.stdout):  # one stream keeps each error under its section
        for argv in CHECKS:
            print(f"== ofa {' '.join(argv)}", flush=True)
            code = cli.main(list(argv))
            print(f"== exit {code}", flush=True)
    return 0
