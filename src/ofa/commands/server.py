"""ofa server start|stop|status: the shared local Odoo server."""
import json

from ofa import config, server


def register(subparsers):
    p = subparsers.add_parser("server", help="start, stop or check the local Odoo server")
    p.add_argument("action", choices=("start", "stop", "status"))
    p.set_defaults(func=handler)


def handler(args):
    cfg = config.load().server
    if args.action == "start":
        return server.start(cfg)
    if args.action == "stop":
        return server.stop(cfg)
    st = server.status(cfg)
    print(json.dumps(st))
    return 0 if st["alive"] and st["port_answers"] else 4
