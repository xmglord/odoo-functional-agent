"""ofa test: run scenarios against a demo target and write the C9 run artifacts."""
import sys

from ofa import client, report, scenario
from ofa.errors import ENVIRONMENT, FUNCTIONAL_FAILURE, OK, UsageError


def register(subparsers):
    p = subparsers.add_parser("test", help="run scenario files against a demo target and write run artifacts")
    p.add_argument("--target", required=True)
    p.add_argument("--plan-dir", help="plan dir; the run goes under PLAN_DIR/runs/ (default ./runs/)")
    p.add_argument("--run", metavar="RUN_ID", help="write into this existing run dir (e.g. the one ofa apply created)")
    p.add_argument("scenarios", nargs="+", metavar="SCENARIO.json")
    p.set_defaults(func=handler)


def exit_code(results):
    statuses = {r["status"] for r in results}
    if scenario.ERROR in statuses:
        return ENVIRONMENT
    if scenario.FAIL in statuses:
        return FUNCTIONAL_FAILURE
    return OK


def handler(args):
    # Validate every file before touching Odoo: a bad file is a usage error (exit 2).
    loaded = [scenario.load(path) for path in args.scenarios]
    ids = [s["id"] for s in loaded]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise UsageError(f"duplicate scenario id {', '.join(dup)}")
    c = client.open_client(args.target)
    run_dir = report.run_dir_for(args.plan_dir, args.run, args.target)
    results, records, shots = [], {}, []
    for sc in loaded:
        result, evidence, sc_shots = scenario.run(c, sc)
        results.append(result)
        if evidence:
            records[sc["id"]] = evidence
        shots += sc_shots
        print(f"{result['status']}\t{sc['id']}", file=sys.stderr)
    report.write_test_run(run_dir, run_dir.name, args.target, results, records, shots, c.call_log, args.plan_dir)
    print(run_dir.name)
    return exit_code(results)
