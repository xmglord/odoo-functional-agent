"""The local Odoo server process shared by all demo targets (C13)."""
import os
import signal
import socket
import subprocess
import time
from urllib.parse import urlsplit

from ofa import config
from ofa.errors import EnvError, GuardError

START_TIMEOUT = 90
STOP_TIMEOUT = 30


def pid_file():
    return config.config_dir() / "server.pid"


def port_answers(url, timeout=2):
    parts = urlsplit(url)
    try:
        with socket.create_connection((parts.hostname, parts.port or 80), timeout=timeout):
            return True
    except OSError:
        return False


def _read_pid():
    try:
        return int(pid_file().read_text().strip())
    except (OSError, ValueError):
        return None


def _is_our_odoo(pid, server):
    """True when pid is alive and is odoo-bin running with our conf (guards against pid reuse)."""
    try:
        argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
    except OSError:
        return False
    args = [a.decode(errors="replace") for a in argv]
    return any(a.endswith("odoo-bin") for a in args) and str(server.odoo_conf) in args


def status(server):
    pid = _read_pid()
    alive = pid is not None and _is_our_odoo(pid, server)
    return {"alive": alive, "pid": pid if alive else None, "port_answers": port_answers(server.url)}


def start(server, log=print):
    problems = config.hardening_problems(server.odoo_conf)
    if problems:
        raise GuardError("SERVER_UNHARDENED", f"{server.odoo_conf}: {'; '.join(problems)}")
    st = status(server)
    if st["alive"] and st["port_answers"]:
        log(f"already running (pid {st['pid']})")
        return 0
    if st["alive"]:
        raise EnvError("SERVER_STARTING", f"pid {st['pid']} is alive but {server.url} does not answer yet; retry or ofa server stop")
    if st["port_answers"]:
        raise EnvError("PORT_IN_USE", f"{server.url} answers but not from an ofa-started server")
    log_file = server.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    # No command-line override of max_cron_threads or dbfilter: the conf decides.
    proc = subprocess.Popen([str(server.python), str(server.odoo_bin), "-c", str(server.odoo_conf), f"--logfile={log_file}"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    pid_file().parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    pid_file().write_text(f"{proc.pid}\n")
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pid_file().unlink(missing_ok=True)
            raise EnvError("SERVER_EXITED", f"odoo-bin exited with {proc.returncode}; see {log_file}")
        if port_answers(server.url):
            log(f"started (pid {proc.pid}), log {log_file}")
            return 0
        time.sleep(0.5)
    raise EnvError("SERVER_TIMEOUT", f"{server.url} did not answer within {START_TIMEOUT} s; see {log_file}")


def stop(server, log=print):
    pid = _read_pid()
    if pid is None or not _is_our_odoo(pid, server):
        pid_file().unlink(missing_ok=True)
        log("not running")
        return 0
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + STOP_TIMEOUT
    while time.monotonic() < deadline and _is_our_odoo(pid, server):
        time.sleep(0.3)
    if _is_our_odoo(pid, server):
        os.kill(pid, signal.SIGKILL)
    pid_file().unlink(missing_ok=True)
    log(f"stopped (pid {pid})")
    return 0
