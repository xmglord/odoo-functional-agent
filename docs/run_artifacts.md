# Run artifacts

Every `ofa apply` or `ofa test` writes into a run directory, `runs/<run_id>/`, where `run_id` is
`YYYYmmddTHHMMSSZ_<target>` (UTC). With a plan dir the runs live in `<plan_dir>/runs/`, otherwise in `./runs/`.

```
ofa test [--plan-dir D] [--run RUN_ID] --target N SCENARIO.json...
```

- Without `--run`, `ofa test` creates a new run dir. With `--run`, it writes into that existing run dir, normally the
  one `ofa apply` just created, so one run holds both the apply and the test results.
- It prints the run id on stdout and one `<status>\t<scenario id>` line per scenario on stderr.
- Exit codes: 0 all pass, 1 any fail, 4 any error, 2 invalid scenario file or unknown `--run`.

## Files

| File | Written by | Contents |
|---|---|---|
| `apply.json` | `ofa apply` | the per-operation results (see [plan_format.md](plan_format.md)) |
| `test.json` | `ofa test` | `{"run_id", "target", "scenarios": [{"id", "status", "steps": [{"id", "status", "message", "records": {"model", "ids"}}], "identities"?: [{"login", "source", "groups"}]}]}`; `identities` only when a step acted `as` a test user |
| `records.json` | `ofa test` | `{scenario id: {evidence label: [rows]}}`; a read-back that failed is `{"error": message}` |
| `screenshot_targets.json` | `ofa test` | `[{"scenario", "label", "model", "id", "url"}]` with `url` = `<server url>/odoo/<model>/<id>` |
| `calls.jsonl` | `ofa test` | one JSON object per Odoo call: `ts`, `model`, `method`, `ids`, `duration_ms`, `status`; appended, so lines already in the run dir are kept |
| `test_history.jsonl` | `ofa test` | one line per `ofa test` invocation into this run: `{"at", "scenarios"}` with that invocation's scenario results; appended |
| `report.md` | `ofa test` | human summary, regenerated from the files above |
| `screenshots/<scenario>_<label>.png` | the skill | screenshots of the `screenshot_targets.json` entries, best effort |
| `files/<scenario>_<file>.<ext>` | `ofa test` | text a `check` step saved with `file` (an exported XML); `records.json` keeps its path under the scenario's `_files` |

A run accumulates per scenario. Each `ofa test` into the same run replaces, in `test.json`, `records.json` and
`screenshot_targets.json`, only the scenarios it ran; the other scenarios' results, evidence and screenshot targets
stay. The latest run of a scenario wins there. `test_history.jsonl` keeps every invocation, and `report.md` lists the
earlier ones with their failing steps, so a fail fixed by a later rerun stays on record.

`report.md` holds the plan title and hash, a table of operations (with `pre-state` marked on operations that already
held on the fresh database), a table of scenarios with the failing step and its message, and links to
`records.json` and to each screenshot that exists. Every link is relative, so a run dir can be copied elsewhere,
for example into `examples/`, and still render.

## What never goes into an artifact

- API keys, request headers, request parameters and error bodies. `calls.jsonl` keeps only the six keys above.
- The `debug` field of Odoo error responses, which carries a server traceback with local paths. Step messages and
  read-back errors are built from the error's `name` and `message` only, as `"<name>: <message>"`.
- `Traceback` text or absolute filesystem paths. As a second line of defence, messages are scrubbed: a traceback is
  replaced by `[traceback removed]` and an absolute path by `<path>`.

## `ofa dump`

```
ofa dump <plan_dir> --target N [--out FILE]
```

`dump` reads `plan.json` and prints what the plan configured on the target as canonical JSON (sorted keys,
two-space indent, trailing newline). Two databases whose dumps are byte-identical hold the same configuration,
which is how repeatability is checked: apply the same frozen plan to two fresh databases and compare.

```json
{
  "modules": ["crm", "sale_management"],
  "settings": {"op_020_settings": {"group_discount_per_so_line": true}},
  "records": {"__ofa__.company_mx": {"model": "res.company", "values": {"country_id": "base.mx", "name": "Demo MX"}}}
}
```

- `modules`: the modules named by `install_modules` operations that are installed, sorted.
- `settings`: for each `set_settings` operation, the current value of each field it sets, read in the operation's
  company.
- `records`: for each `upsert_record` operation, the record behind `__ofa__.<key>` with the fields the plan sets.
  A record that is missing has `"values": null`.
- `call_method` operations are not dumped: their effect shows in the fields of other operations.

Normalization, so database ids never appear:

- many2one and x2many values become external identifiers (`module.name`), preferring the plan's own `__ofa__`
  key, then the alphabetically first one. Identifiers in the `__export__` module are ignored, because their names
  differ between databases.
- A related record with no external identifier becomes `"<model>:<display name>"`.
- x2many values are sorted lists; an empty many2one is `null`.
- `id`, `create_date`, `write_date`, `create_uid` and `write_uid` are never dumped, and only fields named in the
  plan are read.
