# Plan format `ofa.plan/1`

A plan is the reviewable description of a configuration change. The agent writes it, a person reviews
it, `ofa freeze` approves it, and `ofa apply` runs it against a demo database. Applying the same frozen
plan again changes nothing and reports every operation as `unchanged`.

## Plan directory

| File | Written by | Content |
|---|---|---|
| `requirement.md` | agent | The business requirement, verbatim and anonymized |
| `plan.json` | agent | The operations (this document) |
| `plan.md` | agent | The rationale: why each operation exists, citing it as `[op_id]` |
| `plan.approved` | `ofa freeze` | `{"sha256": "<hex>", "approved_at": "<ISO UTC>"}` |
| `scenarios/*.json` | agent | Optional acceptance scenarios |
| `runs/<run_id>/apply.json` | `ofa apply` | The per-operation result of one apply |

## Commands

```
ofa validate <plan_dir> [--target <name>]   # check the rules below; exit 2 on any problem
ofa freeze <plan_dir>                       # validate, then write plan.approved
ofa lint-plan <plan_dir> --target <name>    # check every name in plan.json and plan.md; exit 2 on a plan.json error
ofa apply <plan_dir> --target <name>        # apply the frozen plan; prints the run id
```

- `lint-plan` is read-only. The target is the authority: it reads `ir.module.module`, `ir.model`,
  `ir.model.fields` (not `fields_get`, which hides fields restricted to groups) and `ir.model.data`. A name the
  target lacks is looked up in a static index of the Odoo source the server runs (the addons paths of the Odoo
  conf, Community and Enterprise), because the plan's modules are not installed yet. It reports `NOT_IN_20` (no
  such name in 20.0), `NEEDS_MODULE` (only a module the plan does not install defines it), `BAD_SELECTION`,
  `UNRESOLVED_REF` and `EDITION`. In plan.md it checks dotted names in backticks (`sale.order.state`,
  `base.group_user`) and bare snake_case names (`invoice_policy`); its summary counts what it could not check.
  Names listed in a `<!-- ofa-lint-ignore: a, b -->` comment are skipped, for prose that says a name no longer
  exists.
- Severity: a problem in plan.json is an error and makes `lint-plan` exit 2; a problem in plan.md is a warning
  (`plan.md:<line>: <CODE>: <name>: <reason> (warning)`) and does not change the exit code. plan.json is what
  `apply` runs; prose also names things the checker cannot resolve (context keys, access record names, chart
  template codes) and rejected alternatives from modules the plan does not install, so the reviewer judges
  those. With `--json` every problem carries its `severity`.
- The source index is built on first use and cached in `~/.cache/ofa/` (`$OFA_CACHE_DIR`), keyed by the source
  checkouts' commits. Because it is derived from Enterprise code it never lives in the repository: `lint-plan`
  refuses a cache directory inside it, and the repo hygiene test fails on any tracked or untracked index file.

- `validate` is offline. With `--target` it also checks the target's edition and that every `{"$ref"}`
  exists on the target (read-only). An `__ofa__.<key>` ref is accepted when an operation of the plan
  defines that key.
- `freeze` hashes `plan.json` only. The hash is the SHA-256 of the canonical JSON
  (`json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` in UTF-8), so key order
  and whitespace do not matter. Re-run `freeze` after any review change.
- `apply` exits 2 with `NOT_APPROVED` when `plan.approved` is missing and `HASH_MISMATCH` when
  `plan.json` changed after freezing. Both checks run before any call to Odoo. It exits 0 when no operation
  failed and 1 otherwise. The run id goes to stdout and a one-line status per operation goes to stderr.

## `plan.json`

```json
{
  "format": "ofa.plan/1",
  "title": "Sales discounts and a Mexican subsidiary",
  "odoo_version": "20.0",
  "edition": "community",
  "areas": ["sales_crm", "multi_company"],
  "operations": [ ... ]
}
```

Fields shared by every operation:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | `^op_[a-z0-9_]+$`, unique in the plan |
| `type` | yes | `install_modules`, `set_settings`, `upsert_record` or `call_method` |
| `depends_on` | no | Ids that must run first. Order is topological; ties keep list order |
| `rationale` | yes | One non-empty line |
| `knowledge_refs` | no | Paths to knowledge entries in this repo, optionally with `#anchor` |
| `edition` | no | `community` (default) or `enterprise` |
| `company` | no | A `{"$ref"}` to a company. Its calls run with `allowed_company_ids: [<id>]` in the context |

### Value references

Values may contain references, resolved on the target when the plan is applied:

| Form | Becomes |
|---|---|
| `{"$ref": "module.name"}` | the id of that external id (`base.mx`, or `__ofa__.<key>` for records the plan made) |
| `{"$search": {"model": "m", "domain": [...]}}` | the id of the single matching record; more or fewer is an error |
| `{"$set": [refs...]}` | x2many: exactly these records |
| `{"$add": [refs...]}` | x2many: add these records |

`{"$create"}` is not allowed in plans. A record a plan needs is its own `upsert_record` operation.

### `install_modules`

```json
{"id": "op_010_install_sales", "type": "install_modules", "modules": ["sale_management"],
 "rationale": "Quotations and sales orders come from the Sales app."}
```

`unchanged` when every module is already installed. Otherwise `button_immediate_install` runs on the
missing ones and the status is `created`. An unknown module name fails the operation.

### `set_settings`

```json
{"id": "op_020_line_discounts", "type": "set_settings", "company": {"$ref": "base.main_company"},
 "values": {"group_discount_per_so_line": true}, "depends_on": ["op_010_install_sales"],
 "rationale": "The Discounts setting shows the discount column on sales order lines."}
```

`values` are `res.config.settings` field names. `ofa` opens a settings record in the company's context
and reads the current values. When they all already hold, the status is `unchanged`. Otherwise it saves a
settings record with `values` (like pressing Save in Settings) and the status is `updated`.

### `upsert_record`

```json
{"id": "op_040_company_mx", "type": "upsert_record", "model": "res.company", "key": "company_mx",
 "values": {"name": "Demo MX SA de CV", "country_id": {"$ref": "base.mx"}, "currency_id": {"$ref": "base.MXN"}},
 "match": [["name", "=", "Demo MX SA de CV"]],
 "rationale": "The Mexican subsidiary is a separate company in MXN."}
```

`key` (`^[a-z0-9_]{1,60}$`) names the record as the external id `__ofa__.<key>`. Later operations refer to
it with `{"$ref": "__ofa__.<key>"}`.

- The key exists and every value already matches: `unchanged`.
- The key exists and some values differ: only the differing fields are written, `updated`.
- The key does not exist and the optional `match` domain finds exactly one record: that record gets the
  key and is brought to `values`, `adopted`. When `match` finds more than one record the operation fails;
  make the domain stricter.
- Otherwise the record is created and gets the key, `created`.

When the created record is a `res.company`, `ofa` also adds it to its own bot user's companies, so later
operations can read and write in it.

### The bot user's groups

`ofa` writes as its own user, `ofa_bot`, which provisioning creates with the admin user's groups. A module
installed later gives its groups (Project manager, Employees officer, ...) to the admin only, and the bot would
then get `AccessError` on that module's models. So `ofa apply` brings the bot up to the admin twice:

- at the start of every apply, which also covers modules installed some other way (the UI, another plan);
- right after every `install_modules` operation, before the operations that use the new module.

Each sync adds every group in the admin's `group_ids` that is not in the bot's `all_group_ids` (groups plus
implied groups). It never removes a group and gives the bot nothing the admin does not have. When the bot is
already in sync it writes nothing, so re-applies stay quiet. A failed start sync skips every operation; a
failed sync after `install_modules` fails that operation.

### `call_method`

```json
{"id": "op_050_company_mx_chart", "type": "call_method", "model": "res.company",
 "target": {"$ref": "__ofa__.company_mx"}, "method": "install_l10n_modules", "params": {},
 "skip_if": {"model": "res.company", "min_count": 1,
             "domain": [["id", "=", {"$ref": "__ofa__.company_mx"}], ["chart_template", "=", "mx"]]},
 "wizards": {"some.wizard": "action_apply"}, "depends_on": ["op_040_company_mx"],
 "rationale": "Load the Mexican chart of accounts unless it is already there."}
```

Calls a public record method on `target` with `params` as named arguments. `skip_if` is required: when
`search_count(domain) >= min_count` (default 1) the call is skipped and the status is `unchanged`, which
keeps re-applies idempotent. Otherwise the method runs and the status is `called`.

When the method answers with a wizard (a window action with `target: "new"`), `ofa` calls the wizard's
method from `wizards`, or from its built-in map (`confirm.stock.sms` → `dont_send_sms`,
`stock.backorder.confirmation` → `process`), up to three wizards deep. Any other wizard fails the
operation with `UNHANDLED_WIZARD`.

## Validation rules

`ofa validate` reports every problem it finds, each with one of these codes:

| Code | Rule |
|---|---|
| `BAD_FORMAT` | `format` is `ofa.plan/1`, `odoo_version` is `20.0`, `edition` and `title` are set, `operations` is a non-empty list |
| `BAD_OP` | known `type` and its required fields with the right JSON types |
| `BAD_ID` | `id` matches `^op_[a-z0-9_]+$` |
| `DUPLICATE_ID` | ids are unique |
| `UNKNOWN_DEPENDENCY` | every `depends_on` entry is an id of the plan |
| `CYCLE` | the dependency graph is acyclic |
| `EMPTY_RATIONALE` | `rationale` is not empty |
| `MISSING_KNOWLEDGE_REF` | every `knowledge_refs` path is a file in the repo |
| `OP_NOT_IN_PLAN_MD` | `plan.md` exists and mentions every op as `[op_id]` |
| `BAD_KEY` | an upsert `key` matches `^[a-z0-9_]{1,60}$` |
| `CREATE_NOT_ALLOWED` | no `$create` anywhere in the plan |
| `SKIP_IF_REQUIRED` | every `call_method` has `skip_if` |
| `EDITION_MISMATCH` | with `--target`: no `enterprise` op or plan on a community target |
| `UNRESOLVED_REF` | with `--target`: every `$ref` exists on the target |

## Result statuses (`runs/<run_id>/apply.json`)

| Status | Meaning |
|---|---|
| `created` | Modules installed, or a record created |
| `updated` | Settings saved, or differing fields of a keyed record written |
| `adopted` | An existing record found by `match` was keyed and brought to `values` |
| `unchanged` | The target state already held; nothing was written |
| `called` | The method ran (its `skip_if` did not hold yet) |
| `failed` | The operation raised an error; the run stops here |
| `skipped` | Not attempted because an earlier operation failed |

After every create, write or settings save, `ofa` reads the written values back. A value that did not hold
(Odoo recomputed or rejected it, as it does for a computed stored field such as `res.partner.is_company`)
fails the operation with `VALUE_NOT_HELD`, naming the fields. Without this check such a plan would pass its
first apply and then write the same value again on every re-apply.

`pre_state: true` marks an `unchanged` result on the first apply of the plan to a database (one this plan
dir has no earlier run for), when the operation does not depend on anything this run produced. The state
already held before the plan ran, typically from the template's demo data, so that operation proves
nothing about the plan. `plan.md` and the run report should say so.

An operation depends on this run when it refers (anywhere: `target`, `match`, `values`, `params`,
`skip_if`) to an `{"$ref": "__ofa__.<key>"}` whose upsert was `created`, `updated` or `adopted` earlier in
the same run, or whose upsert itself depends on this run. Such an `unchanged` result has
`pre_state: false`, and `ofa apply` prints it as `unchanged (state produced earlier in this run)`.

Each operation record is:

```json
{"op_id": "op_040_company_mx", "type": "upsert_record", "status": "created", "model": "res.company",
 "res_ids": [7], "pre_state": false, "error": null, "duration_ms": 812}
```

`error` is `"<name>: <message>"` from the error alone: never a server traceback, never a filesystem path.
The file's top level holds `run_id` (`YYYYmmddTHHMMSSZ_<target>`), `plan_sha256`, `target`, `db`,
`db_uuid`, `odoo_version`, `edition`, `started_at`, `finished_at`, `bot_groups` and `ops`.

`bot_groups` lists every sync of the bot's groups, in order:

```json
[{"at": "start", "added": [], "error": null},
 {"at": "op_010_install_project", "added": ["project.group_project_manager"], "error": null}]
```

`added` holds the xmlids of the groups added (`res.groups,<id>` for a group without one). The run fails
when any sync has an `error`.
