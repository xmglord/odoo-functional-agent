"""Local config file: server settings and registered demo targets (C2)."""
import configparser
import json
import os
import tempfile
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from ofa.errors import EnvError, GuardError

SERVER_KEYS = ("odoo_bin", "python", "odoo_conf", "url", "odoo_version", "edition", "template_db",
               "template_modules", "log_file", "xmlid_store")
XMLID_STORES = ("ir_model_data", "config_parameter")
TARGET_KEYS = ("db", "url", "marker", "api_key_file", "created_at", "odoo_version", "edition")
DEFAULT_DATA_DIR = "~/.local/share/Odoo"


def config_dir():
    return Path(os.environ.get("OFA_CONFIG_DIR") or "~/.config/ofa").expanduser()


def config_path():
    return config_dir() / "config.toml"


def _odoo_options(conf_path):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with open(conf_path) as f:
            parser.read_file(f)
    except OSError as e:
        raise EnvError("ODOO_CONF_UNREADABLE", f"cannot read {conf_path}: {e.strerror}") from None
    except configparser.Error as e:
        raise EnvError("ODOO_CONF_INVALID", f"{conf_path}: {type(e).__name__}") from None
    return dict(parser["options"]) if parser.has_section("options") else {}


def hardening_problems(conf_path):
    """Return what keeps the Odoo conf from serving only demo DBs; empty when hardened.

    Shared by `ofa doctor` and `ofa server start` (C13 preconditions).
    """
    opts = _odoo_options(str(conf_path))
    problems = []
    if opts.get("max_cron_threads", "").strip() != "0":
        problems.append("max_cron_threads is not 0")
    if not opts.get("dbfilter", "").strip().startswith("^ofa_demo_"):
        problems.append("dbfilter does not start with ^ofa_demo_")
    if opts.get("list_db", "").strip().lower() not in ("false", "0", "no", "off"):
        problems.append("list_db is not False")
    return problems


@dataclass(frozen=True)
class ServerCfg:
    odoo_bin: Path
    python: Path
    odoo_conf: Path
    url: str
    odoo_version: str
    edition: str
    template_db: str
    template_modules: tuple
    log_file: Path
    xmlid_store: str

    # Postgres access and filestore location come from the Odoo conf itself, so
    # ofa and the server can never disagree about them.
    @property
    def _opts(self):
        return _odoo_options(str(self.odoo_conf))

    @property
    def db_user(self):
        user = self._opts.get("db_user", "").strip()
        if not user:
            raise EnvError("ODOO_CONF_INVALID", f"{self.odoo_conf} has no db_user in [options]")
        return user

    @property
    def db_host(self):
        return self._opts.get("db_host", "").strip() or "127.0.0.1"

    @property
    def db_port(self):
        return int(self._opts.get("db_port", "").strip() or 5432)

    @property
    def data_dir(self):
        return Path(self._opts.get("data_dir", "").strip() or DEFAULT_DATA_DIR).expanduser()


@dataclass(frozen=True)
class Target:
    name: str
    db: str
    url: str
    marker: str
    api_key_file: str
    created_at: str
    odoo_version: str
    edition: str

    def api_key(self):
        path = Path(self.api_key_file).expanduser()
        try:
            key = path.read_text().strip()
        except OSError:
            raise EnvError("KEY_MISSING", f"api key file for target {self.name} is missing or unreadable") from None
        if not key:
            raise EnvError("KEY_MISSING", f"api key file for target {self.name} is empty")
        return key


@dataclass(frozen=True)
class Config:
    server: ServerCfg
    targets: dict = field(default_factory=dict)

    def target(self, name):
        try:
            return self.targets[name]
        except KeyError:
            raise GuardError("NOT_REGISTERED", f"target {name} is not registered") from None


def _invalid(msg):
    return EnvError("CONFIG_INVALID", f"{config_path()}: {msg}")


def _read_raw():
    path = config_path()
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise EnvError("CONFIG_MISSING", f"{path} not found; copy config/ofa_config.toml.example there") from None
    except OSError as e:
        raise EnvError("CONFIG_UNREADABLE", f"cannot read {path}: {e.strerror}") from None
    except tomllib.TOMLDecodeError as e:
        raise _invalid(f"not valid TOML ({e})") from None


def _parse_server(raw):
    server = raw.get("server")
    if not isinstance(server, dict):
        raise _invalid("missing [server] table")
    missing = [k for k in SERVER_KEYS if k not in server]
    if missing:
        raise _invalid(f"[server] is missing {', '.join(missing)}")
    if server["xmlid_store"] not in XMLID_STORES:
        raise _invalid(f"server.xmlid_store must be one of {', '.join(XMLID_STORES)}")
    values = {k: server[k] for k in SERVER_KEYS}
    for k in ("odoo_bin", "python", "odoo_conf", "log_file"):
        values[k] = Path(values[k]).expanduser()
    values["template_modules"] = tuple(values["template_modules"])
    return ServerCfg(**values)


def _parse_targets(raw):
    targets = {}
    for name, t in (raw.get("targets") or {}).items():
        missing = [k for k in TARGET_KEYS if k not in t]
        if missing:
            raise _invalid(f"[targets.{name}] is missing {', '.join(missing)}")
        targets[name] = Target(name=name, **{k: t[k] for k in TARGET_KEYS})
    return targets


def load():
    raw = _read_raw()
    return Config(server=_parse_server(raw), targets=_parse_targets(raw))


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    # JSON string escapes are valid TOML basic-string escapes.
    return json.dumps(str(v), ensure_ascii=False)


def dumps(raw):
    """Serialize the flat C2 schema: [server] plus [targets.<name>] tables."""
    lines = ["[server]"]
    lines += [f"{k} = {_toml_value(v)}" for k, v in raw.get("server", {}).items()]
    for name, t in raw.get("targets", {}).items():
        lines += ["", f"[targets.{name}]"]
        lines += [f"{k} = {_toml_value(v)}" for k, v in t.items()]
    return "\n".join(lines) + "\n"


def _write_raw(raw):
    d = config_dir()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(dumps(raw))
        os.chmod(tmp, 0o600)
        os.replace(tmp, config_path())
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def add_target(target):
    raw = _read_raw()
    raw.setdefault("targets", {})[target.name] = {f.name: getattr(target, f.name) for f in fields(Target) if f.name != "name"}
    _write_raw(raw)


def remove_target(name):
    raw = _read_raw()
    if (raw.get("targets") or {}).pop(name, None) is None:
        raise GuardError("NOT_REGISTERED", f"target {name} is not registered")
    _write_raw(raw)
