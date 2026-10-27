"""ofa source: where the Odoo source the server runs lives, for reading names and behaviour (T24)."""
import json

from ofa import config
from ofa.errors import EnvError
from ofa.source_index import addons_roots


def register(subparsers):
    p = subparsers.add_parser("source", help="print the Odoo source directories the server runs")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=handler)


def handler(args):
    server = config.load().server
    roots, odoo_pkg = addons_roots(server)
    if not roots:
        raise EnvError("SOURCE_MISSING", "no addons directory found from the Odoo conf's addons_path")
    rows = [{"kind": "addons", "path": str(r)} for r in roots]
    if odoo_pkg.is_dir():
        rows.append({"kind": "core", "path": str(odoo_pkg)})
    if args.json:
        print(json.dumps({"odoo_version": server.odoo_version, "edition": server.edition, "paths": rows}, indent=2))
    else:
        for r in rows:
            print(f"{r['kind']}\t{r['path']}")
    return 0
