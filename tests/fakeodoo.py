"""A scriptable fake of Odoo's /json/2/<model>/<method> endpoint for unit tests.

Usage:
    with FakeOdoo(key="k", db="ofa_demo_t") as fake:
        fake.script("res.partner", "search", [1, 2])          # static result
        fake.script("x.y", "z", lambda req: Response(404, "<html>", "text/html"))
        fake.script("a.b", "c", [r1, r2], sequence=True)     # one result per call
        ... fake.url, fake.requests

Unscripted calls get a 500 JSON error. The fake enforces the C3 parameter
names for the primitives it knows and rejects non-empty `ids` on @api.model
primitives, both with 422 UnprocessableEntity, as the real server does.
"""
import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UNPROCESSABLE = "werkzeug.exceptions.UnprocessableEntity"

# primitive -> (is @api.model, allowed named params)
PRIMITIVES = {
    "create": (True, {"vals_list"}),
    "write": (False, {"vals"}),
    "read": (False, {"fields", "load"}),
    "search_read": (True, {"domain", "fields", "limit", "offset", "order"}),
    "search": (True, {"domain", "limit", "offset", "order"}),
    "search_count": (True, {"domain", "limit"}),
    "fields_get": (True, {"allfields", "attributes"}),
    "get_str": (True, {"key"}),
    "context_get": (True, set()),
}


@dataclass
class Response:
    status: int
    body: object
    content_type: str = "application/json"


@dataclass
class Request:
    model: str
    method: str
    headers: dict
    body: dict

    @property
    def ids(self):
        return self.body.get("ids")

    @property
    def context(self):
        return self.body.get("context")

    @property
    def params(self):
        return {k: v for k, v in self.body.items() if k not in ("ids", "context")}


def error_body(name, message, debug=None):
    body = {"name": name, "message": message, "arguments": [message], "context": {}}
    if debug is not None:
        body["debug"] = debug
    return body


class FakeOdoo:
    def __init__(self, key="test-key", db="ofa_demo_test"):
        self.key = key
        self.extra_keys = set()  # other users' keys the server also accepts (test identities)
        self.db = db
        self.requests = []
        self._scripts = {}
        self._sequence = set()
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    def script(self, model, method, result, sequence=False):
        self._scripts[(model, method)] = list(result) if sequence else [result]
        if sequence:
            self._sequence.add((model, method))
        else:
            self._sequence.discard((model, method))

    def calls(self, model=None, method=None):
        return [r for r in self.requests
                if (model is None or r.model == model) and (method is None or r.method == method)]

    def _respond(self, req):
        if req.headers.get("authorization") not in {f"bearer {k}" for k in {self.key, *self.extra_keys}}:
            return Response(401, error_body("werkzeug.exceptions.Unauthorized", "Invalid apikey"))
        if req.headers.get("x-odoo-database") != self.db:
            return Response(404, "<!doctype html><title>404 Not Found</title>", "text/html")
        spec = PRIMITIVES.get(req.method)
        if spec:
            is_model, allowed = spec
            unknown = set(req.params) - allowed
            if unknown:
                return Response(422, error_body(UNPROCESSABLE, f"got an unexpected keyword argument '{sorted(unknown)[0]}'"))
            if is_model and req.ids:
                return Response(422, error_body(UNPROCESSABLE, f"{req.method} does not take ids"))
            if req.method == "create" and "vals_list" not in req.params:
                return Response(422, error_body(UNPROCESSABLE, "missing a required argument: 'vals_list'"))
        with self._lock:
            queue = self._scripts.get((req.model, req.method))
            if not queue:
                return Response(500, error_body("fakeodoo.NotScripted", f"{req.model}/{req.method} is not scripted"))
            result = queue.pop(0) if (req.model, req.method) in self._sequence else queue[0]
        if callable(result):
            result = result(req)
        return result if isinstance(result, Response) else Response(200, result)

    def _handler_class(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                parts = self.path.split("/")
                if len(parts) != 5 or parts[1:3] != ["json", "2"]:
                    return self._send(Response(404, "<html>not found</html>", "text/html"))
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    return self._send(Response(400, error_body("werkzeug.exceptions.BadRequest", "invalid JSON")))
                req = Request(parts[3], parts[4], {k.lower(): v for k, v in self.headers.items()}, body)
                fake.requests.append(req)
                self._send(fake._respond(req))

            def _send(self, resp):
                data = resp.body if isinstance(resp.body, str) and resp.content_type != "application/json" else json.dumps(resp.body)
                data = data.encode()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        return Handler
