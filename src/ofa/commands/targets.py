"""ofa targets: list registered demo targets (never their keys)."""
import json

from ofa import config

FIELDS = ("db", "url", "created_at", "odoo_version", "edition")


def register(subparsers):
    p = subparsers.add_parser("targets", help="list registered demo targets")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=handler)


def handler(args):
    targets = config.load().targets
    rows = [{"name": name, **{f: getattr(t, f) for f in FIELDS}} for name, t in sorted(targets.items())]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r['name']}\t{r['db']}\t{r['url']}\t{r['edition']}\t{r['created_at']}")
    return 0
