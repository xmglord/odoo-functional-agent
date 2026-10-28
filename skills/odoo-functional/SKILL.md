---
name: odoo-functional
description: Turn a business requirement into an Odoo 20 functional configuration on a local demo database. Writes a reviewable plan (plan.json plus a plan.md rationale), stops for the user's approval, then applies it with ofa, runs functional test scenarios and reports pass/fail with evidence. Use when the user describes a business need to configure in Odoo ("we sell with discounts and need approval", "set up two companies that invoice each other", "configure Mexican invoicing"), asks to set up, configure or test sales, CRM, purchase, inventory, accounting, multi-company or Mexican localization in Odoo, or asks to apply or test an Odoo configuration plan.
---

# Odoo functional configuration

You take a business requirement, decide what to configure in Odoo 20, explain each decision so the user learns the
functional side, apply the configuration to a demo database and prove it with functional tests.

Everything that touches Odoo goes through the `ofa` CLI. It is on the Bash PATH while this plugin is enabled, so
run it as plain `ofa <subcommand>`. `ofa` refuses any database that is not a registered, marked demo database on
loopback, and a hook blocks direct `psql`, `odoo-bin` and HTTP access to Odoo.

Reference material in this plugin:
- Knowledge compendium: `${CLAUDE_PLUGIN_ROOT}/knowledge/20.0/INDEX.md` (start here), entry rules in
  `${CLAUDE_PLUGIN_ROOT}/knowledge/README.md`, including the "Known 20.0 drifts" list.
- Plan format: `${CLAUDE_PLUGIN_ROOT}/docs/plan_format.md`.
- Scenario format: `${CLAUDE_PLUGIN_ROOT}/docs/scenario_format.md`.
- Library scenarios: `${CLAUDE_PLUGIN_ROOT}/scenarios/20.0/<area>/*.json`.
- Rationale template: [plan_md_template.md](plan_md_template.md).
- Screenshot procedure: [screenshots.md](screenshots.md).
- Odoo 20.0 source (read-only, for names and behaviour the knowledge does not cover): `ofa source` prints the
  addons directories the server runs (`addons`) and the core package with the ORM (`core`). Read and grep there.

Areas (folder names): `sales_crm`, `purchase_inventory`, `accounting`, `multi_company`, `l10n_mx`.

`ofa` exit codes: 0 ok, 1 functional failure (an op or an assertion failed), 2 usage or validation error,
3 guard refusal, 4 Odoo, connection or environment error.

## Rules

These hold in every phase.

- Never call Odoo except through `ofa`. No `psql`, `odoo-bin`, `curl` to the server, Python scripts that talk to
  Odoo, or edits to the `ofa` config and key files. If the hook or `ofa` refuses something, do not look for another
  way in: tell the user what was refused and why.
- Never navigate the browser anywhere except the loopback demo server (`127.0.0.1`, `localhost`) and the docs
  allowlist (`https://www.odoo.com/documentation/...`, `https://github.com/odoo/...`).
- Never fill a knowledge gap from memory of Odoo 19 or earlier without checking it with `ofa inspect` on the demo
  target. Many names changed in 20.0 (see "Known 20.0 drifts" in the knowledge README). When no entry covers a
  decision, say so in plan.md and mark that decision as uncited.
- When a requirement needs configuration that only the UI can do (no field, setting or method reachable through
  `ofa`), say so explicitly in plan.md and in the report, with the menu path. Do not hide it, and do not do it
  yourself in the browser.
- Use only fictional data: no real company, person, tax id (RFC, CURP), bank or address data, in files or in the
  demo database.
- Never run `ofa freeze` or `ofa apply` before the review stop below has received the user's approval.
- Do not read the plugin repository's `CLAUDE.md` or its local planning notes: they are the maintainer's notes
  about building this tool, not reference material for a requirement. What you need is listed above; the Odoo
  source path comes from `ofa source`.

## Phase 1: Preflight

1. Run `ofa doctor`. Fix nothing by hand; if it reports a problem, show it to the user and stop.
2. Run `ofa server start`. It is idempotent: `already running` is fine. Exit 3 (`SERVER_UNHARDENED`) means the
   server config is unsafe; stop and tell the user.
3. Choose a slug for this requirement: lowercase letters, digits and `_`, at most 40 characters
   (`^[a-z0-9_]{1,40}$`), e.g. `sales_discounts`. It names both the plan directory and the demo target.
4. Target: if the user names an existing target, check it with `ofa targets` and `ofa doctor --target <name>` and
   use it. Otherwise run `ofa provision <slug>` to get a fresh demo database from the template. If the target
   already exists, ask whether to reuse it or reset it (`ofa reset <slug>`); never reset without a yes.
5. Note the target's edition (`ofa targets --json`). Enterprise-only operations are not allowed on a community
   target.

## Phase 2: Intake

1. Create `plans/<slug>/` in the current working directory and save the requirement to
   `plans/<slug>/requirement.md`, verbatim except for anonymization.
2. Replace every real company, person, RFC, CURP, bank account and address with fictional values, and tell the user
   which replacements you made.
3. When the requirement leaves a decision open that changes the configuration (for example: one company or two,
   lots or serial numbers, who approves discounts), ask at most 3 clarifying questions. Do not ask about anything
   the compendium or a sensible default settles; state the default in plan.md instead.

## Phase 3: Plan

1. Read `${CLAUDE_PLUGIN_ROOT}/knowledge/20.0/INDEX.md`, then the index of each area involved
   (`knowledge/20.0/<area>/INDEX.md`), then the relevant entries. Use grep on the entries' front matter
   (`modules:`, `models:`, `settings:`) to find topics. An area index that does not exist yet means that area has no
   entries.
2. Confirm every technical name you are not certain of on the target, read-only:
   - `ofa inspect --target <slug> <model> --fields a,b` for fields of a model
   - `ofa inspect --target <slug> <substring> --settings` for `res.config.settings` fields
   - `ofa inspect --target <slug> <model> --search '<domain json>'` for sample records and their xmlids
   Also check the pre-state: a setting or record the template already has makes that op report `unchanged` on the
   first apply, which proves nothing about the plan.
3. Write `plans/<slug>/plan.json` in the `ofa.plan/1` format (see `docs/plan_format.md`):
   - op types: `install_modules`, `set_settings`, `upsert_record`, `call_method`
   - every op has an `id` matching `^op_[a-z0-9_]+$` (number them `op_010_...`, `op_020_...`), `depends_on`, a
     one-line `rationale`, `knowledge_refs` (paths such as `knowledge/20.0/sales_crm/<topic>.md`, optional
     `#anchor`; leave the list empty only for an uncited decision) and `edition`
   - `upsert_record` needs a `key` (`^[a-z0-9_]{1,60}$`; later ops refer to it as `{"$ref": "__ofa__.<key>"}`) and
     a `match` domain for adopting an existing record
   - `call_method` needs `skip_if`, so a re-apply reports `unchanged`
   - no `$create` in plan values
   - roles: when a need depends on who acts (an approval limit, what a user may see or do), every scenario still
     runs as `ofa_bot`, an administrator that skips approvals. Give the role to a test user with its own op: an
     `upsert_record` of `res.users` with `match` on `login` = `ofa_user_1` (to `ofa_user_3`) and `group_ids` /
     `company_ids` as `$set` (see "Test identities" in `docs/plan_format.md`). Never an administrator group.
4. Write `plans/<slug>/plan.md` from [plan_md_template.md](plan_md_template.md). Every op id must appear in it as the
   literal `[op_id]`, each in its own brackets. Its "Test plan" lists every need of the requirement with the scenario
   you will write for it and what that scenario checks (fields read back, expected values; for a negative test, the
   refusal's exception class and text). Mark a need no scenario will prove as **Not tested**, with the reason; do not
   leave a need out. A report or an exported file is testable with `check` steps (Phase 6), not "read in the UI". List
   the role ops in its "Test identities" section.
5. Run `ofa validate plans/<slug> --target <slug>` and fix the plan until it exits 0.
6. Plan lint: run `ofa lint-plan plans/<slug> --target <slug>`. It checks every module, model, field, settings
   key, method, xmlid and selection value in plan.json, and every technical name in backticks in plan.md, against
   the target and the 20.0 source, so names remembered from older Odoo versions are caught before the review stop.
   - **plan.json errors block.** Fix the plan until `lint-plan` exits 0, then re-run `ofa validate`:
     `NOT_IN_20` (find the 20.0 name with `ofa inspect` or the knowledge entries), `NEEDS_MODULE` (install that
     module or drop the name), `BAD_SELECTION`, `UNRESOLVED_REF`, `EDITION` (fix the value, the reference or the
     edition).
   - **plan.md lines are warnings** (`plan.md:<line>: <CODE>: <name>: <reason> (warning)`). They do not block,
     because prose also names things the linter cannot resolve (context keys, access record names, template
     codes). Do not reword the prose, drop a name or add an ignore comment to make a warning go away; the
     reviewer judges them. Keep every warning of the last run for the "Names to review" section of the review
     stop. The only ignore comment allowed is for a name the prose mentions on purpose as no longer existing
     (`groups_id` in "`res.users.group_ids` (`groups_id` no longer exists)"): list it in
     `<!-- ofa-lint-ignore: name1, name2 -->` in plan.md so it does not clutter that list.
   The summary line counts the plan.md names it could not check (bare names without an underscore, paths, names
   outside backticks); write technical names in backticks with their model (`sale.order.state`) so they get
   checked.

## Phase 4: Review stop

Show the user the full plan.md (including its "Test plan", so the user approves knowing which needs will and will
not be tested), the list of operations (id, type, one line each), the plan directory path and a
section **"Names to review"**: every plan.md warning of the last `ofa lint-plan` run, one per line with its plan.md
line number, the name and the linter's reason (or "none" when there are no warnings). Then stop and wait for an
explicit approval message from the user, such as "approved" or "yes, apply it". A question, a comment, silence, or
approval given for an earlier version is not approval. Never run `ofa freeze` or `ofa apply` without that approval
message in the conversation, even if the user asked earlier to "do everything". A changed plan needs approval
again: if you edit plan.json or a decision in plan.md for any reason (user feedback, a validation error, a failed
apply), re-run `ofa validate` and `ofa lint-plan`, show the changes and the new "Names to review", and wait for a
new approval. Keep the exact approval message; the report quotes it.

## Phase 5: Apply

Only after the approval:

1. `ofa freeze plans/<slug>` records the approved plan's hash in `plan.approved`.
2. `ofa apply plans/<slug> --target <slug>` applies it. It prints the `run_id` on stdout; keep it. The per-op
   results are in `plans/<slug>/runs/<run_id>/apply.json`
   (`created | updated | adopted | unchanged | called | failed | skipped`).

When apply does not exit 0:
- exit 1: the first failed op stopped the run and the rest are `skipped`. Show the op and its `error`. Fixing it
  means changing the plan, which goes back to the review stop.
- exit 2 with `NOT_APPROVED` or `HASH_MISMATCH`: plan.json changed after approval. Go back to the review stop; do
  not re-freeze on your own.
- exit 3: guard refusal. Stop and tell the user; never work around it.
- exit 4: environment problem. Run `ofa doctor` and `ofa server start`, then retry once.

## Phase 6: Test

1. Follow the approved "Test plan" in plan.md. Pick the library scenarios in
   `${CLAUDE_PLUGIN_ROOT}/scenarios/20.0/<area>/` that cover its rows.
2. Write requirement-specific scenarios, one per Test plan row or group of rows, with the checks the row names
   (format `ofa.scenario/1`, see `docs/scenario_format.md`), into `plans/<slug>/scenarios/`. A check that turns out
   impossible or different from the Test plan is a difference to report in Phase 8. Check identifiers they use
   (partners, products, xmlids) with `ofa inspect`. Assertions read fields back; they never call helper methods. A
   scenario only exercises the configuration: it must not change settings to make itself pass. A step that must
   run as a role says `"as": {"$ref": "__ofa__.<role key>"}`; leave the manager's or admin's steps as the bot. Use
   the scenario's own `users` only when the plan defines no role, and say in the report that such a test proves
   the scenario's assumption, not the plan. A negative test (a role must not be able to do something) is a step
   with `expect_error`: the exact Odoo exception class and an English text copied from the 20.0 source or from a
   run, never guessed, and never a test whose "expected result is fail". When the source message is a template
   (the operation, model or record is filled in at run time, as in access errors), do not fill it in yourself:
   which check refuses first decides the words (a user who cannot read a record is refused with the "read" text
   even when the step writes). Take the text from a run (the step once without `expect_error`, then the message
   in `test.json`), or keep only the fixed part of the template. After the refused step, read back that
   nothing changed when that applies (the tax amount is unchanged, no entry was created). When the plan works in
   a company other than the main one, set the scenario's top-level `company` to it: without it, reads and
   company-dependent values (a customer's `total_due`) follow `ofa_bot`'s default company. Never change `ofa_bot`'s
   companies in a scenario.
   A report's figures or an exported file (a P&L across companies, the SAT XML) are not records: get the report's
   options with a `call` to `account.report` `get_options` and `save_as`, pass them on (`{"$var": "opts"}`) to the
   call that produces the lines or the file, `save_as` that too, and assert on it with `check` steps (`path`,
   `xml`, `expect`; see "Checking a saved result" in `docs/scenario_format.md`). Never mark such a need "read in
   the UI" or Not tested before trying this. Use `check` only for report options, report lines and exported files;
   anything a user sees on a record is a field, checked with `assert`.
3. Run them into the same run:
   `ofa test --plan-dir plans/<slug> --run <run_id> --target <slug> <scenario.json> ...`
   Exit 0 means all pass, 1 means an assertion failed, 4 means a scenario errored (its preconditions failed or the
   environment broke). Do not edit a scenario's expectations to turn a fail into a pass; report the fail, find the
   cause, and if the plan is wrong, change it and go back to the review stop.
4. When the cause is a mistake in how you wrote the scenario (a wrong field, a wrong comparison), fix the scenario
   and run it again **in full**. Never replace it with a read-only recheck of what the failed run left behind: the
   fixed file has then never passed. If the records it already created make a full rerun collide, run it on a fresh
   database: `ofa provision <slug>_2`, `ofa apply` of the same frozen plan, then `ofa test` of every scenario into
   that apply's run. If that is not possible, say in the report that the fixed scenario never ran.

## Phase 7: Evidence

Follow [screenshots.md](screenshots.md). Screenshots are best-effort: if any step fails, or the procedure is not
available, say so, and the evidence is the records read back in `runs/<run_id>/records.json`.

## Phase 8: Report

Tell the user, in this order:
1. Plan title, the approval message you received (quoted) and the run id.
2. Operations: counts per status, and any op with `"pre_state": true` called out as proving nothing (it already
   held in the template).
3. Scenarios: the Test plan table again, with a result column (pass, fail with the failing step and message,
   or Not tested) for every need. Then list every difference from the approved Test plan: a check dropped or
   weakened, a scenario added or split, a need that moved to Not tested, and why. "No differences" when there
   are none.
4. A link to `plans/<slug>/runs/<run_id>/report.md` (it links `records.json` and the screenshots).
5. Anything that needs UI-only configuration, and every uncited decision.
6. **What you learned**: a short summary of the functional decisions and why each was made, in business terms,
   with the technical names next to them.
7. Cleanup offer: the demo database stays until the user drops it. Offer `ofa drop <slug>` (and `<slug>_2` if
   you made one) and run it only if the user says yes.
