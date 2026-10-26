"""ofa inspect: read-only look at a model's fields, settings and sample records."""
import json

from ofa import client
from ofa.errors import UsageError

ATTRIBUTES = ["string", "type", "relation", "selection"]
SETTINGS_MODEL = "res.config.settings"


def register(subparsers):
    p = subparsers.add_parser("inspect", help="read-only: fields, settings and sample records of a model")
    p.add_argument("--target", required=True)
    p.add_argument("model", help="model name, or with --settings a substring of settings field names")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--fields", help="comma-separated field names")
    g.add_argument("--all-fields", action="store_true", help="describe every field (default)")
    p.add_argument("--settings", action="store_true", help=f"list {SETTINGS_MODEL} fields whose name contains MODEL")
    p.add_argument("--search", metavar="DOMAIN_JSON", help="also return sample records matching this domain")
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=handler)


def handler(args):
    names = [f.strip() for f in args.fields.split(",") if f.strip()] if args.fields else None
    domain = None
    if args.search is not None:
        try:
            domain = json.loads(args.search)
        except ValueError:
            raise UsageError("--search must be a JSON domain, e.g. '[[\"name\",\"ilike\",\"x\"]]'") from None
        if not isinstance(domain, list):
            raise UsageError("--search must be a JSON list")
    c = client.open_client(args.target)
    model = SETTINGS_MODEL if args.settings else args.model
    params = {"attributes": ATTRIBUTES}
    if names:
        params["allfields"] = names
    described = c.call(model, "fields_get", **params)
    if args.settings:
        described = {k: v for k, v in described.items() if args.model in k}
    out = {"model": model, "fields": {k: described[k] for k in sorted(described)}}
    if domain is not None:
        out["records"] = c.call(model, "search_read", domain=domain, fields=names or ["display_name"], limit=args.limit)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0
