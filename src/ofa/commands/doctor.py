"""ofa doctor: one OK/FAIL line per environment check."""
import socket
import sys
from urllib.parse import urlsplit

from ofa import client, config, guard
from ofa.errors import ENVIRONMENT, OK, OfaError


def register(subparsers):
    p = subparsers.add_parser("doctor", help="check the local environment and, optionally, one target")
    p.add_argument("--target", help="also check this target's marker and API access")
    p.set_defaults(func=handler)


def _port_answers(url):
    parts = urlsplit(url)
    try:
        with socket.create_connection((parts.hostname, parts.port or 80), timeout=3):
            return True
    except OSError:
        return False


class Report:
    def __init__(self):
        self.code = OK

    def line(self, ok, name, detail="", code=ENVIRONMENT):
        print(f"{'OK' if ok else 'FAIL'}\t{name}" + (f"\t{detail}" if detail else ""))
        if not ok:
            self.code = max(self.code, code)
        return ok


def handler(args):
    r = Report()
    r.line(sys.version_info >= (3, 11), "python >= 3.11", "%d.%d" % sys.version_info[:2])
    try:
        cfg = config.load()
    except OfaError as e:
        r.line(False, "config readable", f"{e.label}: {e.msg}", e.exit_code)
        return r.code
    r.line(True, "config readable", str(config.config_path()))
    try:
        problems = config.hardening_problems(cfg.server.odoo_conf)
        r.line(not problems, "odoo conf hardened", "; ".join(problems) or str(cfg.server.odoo_conf))
    except OfaError as e:
        r.line(False, "odoo conf hardened", f"{e.label}: {e.msg}", e.exit_code)
    server_up = r.line(_port_answers(cfg.server.url), "server port answers", cfg.server.url)
    if args.target:
        if not server_up:
            # The static checks need no server; the marker check does.
            try:
                guard.check_static(cfg.target(args.target))
                r.line(False, f"target {args.target} marker", "not checked: server down")
            except OfaError as e:
                r.line(False, f"target {args.target}", f"{e.label}: {e.msg}", e.exit_code)
            return r.code
        try:
            c = client.open_client(args.target, cfg=cfg)
            r.line(True, f"target {args.target} marker", c.target.db)
            c.call("res.users", "context_get")
            r.line(True, f"target {args.target} api", "res.users/context_get")
        except OfaError as e:
            r.line(False, f"target {args.target}", f"{e.label}: {e.msg}", e.exit_code)
    return r.code
