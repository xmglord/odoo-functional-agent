"""Run artifacts (C9): writers for test.json, records.json, screenshot_targets.json,
calls.jsonl, and the human summary report.md.

Every link in report.md is relative to the run dir, so a run dir can be copied
(e.g. into examples/) and still render.
"""
import json
import os
import re
import tempfile
import time
from pathlib import Path

from ofa.errors import UsageError
from ofa.scenario import scrub

TEST_JSON = "test.json"
APPLY_JSON = "apply.json"
RECORDS_JSON = "records.json"
SHOTS_JSON = "screenshot_targets.json"
CALLS_JSONL = "calls.jsonl"
REPORT_MD = "report.md"
SCREENSHOTS = "screenshots"
CALL_LOG_KEYS = ("ts", "model", "method", "ids", "duration_ms", "status")


def new_run_id(target, now=None):
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now)) + f"_{target}"


def runs_root(plan_dir=None):
    return (Path(plan_dir) if plan_dir else Path.cwd()) / "runs"


def run_dir_for(plan_dir, run_id, target, now=None):
    """The dir for --run RUN_ID (must exist), or a new run dir."""
    root = runs_root(plan_dir)
    if run_id:
        d = root / run_id
        if not d.is_dir():
            raise UsageError(f"run {run_id} not found under {root.name}/")
        return d
    root.mkdir(parents=True, exist_ok=True)
    d = root / new_run_id(target, now)
    d.mkdir()
    return d


def write_json(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def append_calls(run_dir, call_log):
    """Append the C3 call log; only its whitelisted keys are written."""
    with open(Path(run_dir) / CALLS_JSONL, "a", encoding="utf-8") as f:
        for entry in call_log:
            f.write(json.dumps({k: entry.get(k) for k in CALL_LOG_KEYS}, sort_keys=True) + "\n")


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _cell(value):
    text = scrub("" if value is None else value)
    return text.replace("|", "\\|") or " "


def screenshot_name(scenario_id, label):
    """`<scenario>_<label>.png`, with the label in snake_case so the file name needs no escaping."""
    slug = re.sub(r"[^a-z0-9]+", "_", str(label).lower()).strip("_")
    return f"{scenario_id}_{slug}.png"


def render(run_dir, plan_dir=None):
    run_dir = Path(run_dir)
    apply = _load(run_dir / APPLY_JSON)
    test = _load(run_dir / TEST_JSON)
    records = _load(run_dir / RECORDS_JSON) or {}
    shots = _load(run_dir / SHOTS_JSON) or []
    plan = _load(Path(plan_dir) / "plan.json") if plan_dir else None
    approved = _load(Path(plan_dir) / "plan.approved") if plan_dir else None

    lines = [f"# Run {run_dir.name}", ""]
    target = (test or {}).get("target") or (apply or {}).get("target")
    if target:
        db = (apply or {}).get("db")
        lines.append(f"- Target: `{target}`" + (f" (db `{db}`)" if db else ""))
    title = plan.get("title") if isinstance(plan, dict) else None
    sha = (apply or {}).get("plan_sha256") or (approved or {}).get("sha256")
    if title or sha:
        lines.append(f"- Plan: {_cell(title or '(untitled)')}" + (f", sha256 `{sha}`" if sha else ""))
    if apply and apply.get("odoo_version"):
        lines.append(f"- Odoo {apply['odoo_version']} {apply.get('edition', '')}".rstrip())
    lines.append("")

    lines += ["## Operations", ""]
    ops = (apply or {}).get("ops") or []
    if ops:
        lines += ["| Op | Type | Status | Model | Records | Error |", "|---|---|---|---|---|---|"]
        for op in ops:
            status = op.get("status", "")
            if op.get("pre_state"):
                status += " (pre-state)"
            ids = ", ".join(str(i) for i in op.get("res_ids") or [])
            lines.append(f"| {_cell(op.get('op_id'))} | {_cell(op.get('type'))} | {_cell(status)} | "
                         f"{_cell(op.get('model'))} | {_cell(ids)} | {_cell(op.get('error'))} |")
        if any(op.get("pre_state") for op in ops):
            lines += ["", "Ops marked pre-state already held on the fresh database, so they prove nothing about the plan."]
    else:
        lines.append("No apply in this run.")
    lines.append("")

    lines += ["## Scenarios", ""]
    scenarios = (test or {}).get("scenarios") or []
    if scenarios:
        lines += ["| Scenario | Status | Failing step | Message |", "|---|---|---|---|"]
        for sc in scenarios:
            bad = next((s for s in sc.get("steps", []) if s.get("status") in ("fail", "error")), None)
            lines.append(f"| {_cell(sc.get('id'))} | {_cell(sc.get('status'))} | "
                         f"{_cell(bad and bad.get('id'))} | {_cell(bad and bad.get('message'))} |")
    else:
        lines.append("No scenarios in this run.")
    lines.append("")

    lines += ["## Evidence", ""]
    shot_labels = {(s.get("scenario"), s.get("label")) for s in shots}
    items = [(sc, label) for sc in sorted(records) for label in sorted(records[sc] or {})]
    if items:
        for sc, label in items:
            entry = f"- {_cell(sc)} / {_cell(label)}: [records]({RECORDS_JSON})"
            name = screenshot_name(sc, label)
            if (sc, label) in shot_labels:
                if (run_dir / SCREENSHOTS / name).is_file():
                    entry += f", [screenshot]({SCREENSHOTS}/{name})"
                else:
                    entry += ", screenshot not taken"
            lines.append(entry)
    else:
        lines.append("No evidence in this run.")
    lines.append("")
    return "\n".join(lines)


def write_report(run_dir, plan_dir=None):
    path = Path(run_dir) / REPORT_MD
    path.write_text(render(run_dir, plan_dir), encoding="utf-8")
    return path


def write_test_run(run_dir, run_id, target, results, records, shots, call_log, plan_dir=None):
    """Write every artifact `ofa test` owns into run_dir and regenerate report.md."""
    run_dir = Path(run_dir)
    write_json(run_dir / TEST_JSON, {"run_id": run_id, "target": target, "scenarios": results})
    write_json(run_dir / RECORDS_JSON, records)
    write_json(run_dir / SHOTS_JSON, shots)
    append_calls(run_dir, call_log)
    return write_report(run_dir, plan_dir)
