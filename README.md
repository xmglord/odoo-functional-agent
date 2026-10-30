# odoo-functional-agent

A Claude Code plugin that takes a written business requirement, decides how to configure Odoo 20 to meet it,
explains each decision, applies the configuration to a local **demo** database and proves it with functional
tests. Everything it changes in Odoo goes through one small CLI, `ofa`, that refuses any database it did not
create.

It is a functional consultant's loop made reviewable: the requirement becomes a plan you read and approve before
anything is applied, the plan becomes an idempotent set of operations, and the result is a run report with the
records each test read back and screenshots of them.

## 60-second tour

Open [examples/sales_crm_quote_to_cash/](examples/sales_crm_quote_to_cash/README.md) and read, in this order:

1. [requirement.md](examples/sales_crm_quote_to_cash/requirement.md): what the business asked for, in its words.
2. [plan.md](examples/sales_crm_quote_to_cash/plan.md): each decision with its business reason, what Odoo does,
   the alternatives, the pitfalls and its sources, plus the Test plan (which test proves which need).
3. [plan.json](examples/sales_crm_quote_to_cash/plan.json): the operations `ofa` applied.
4. A [run report](examples/sales_crm_quote_to_cash/runs/20261027T165302Z_t21/report.md): every operation's status,
   every scenario's result, the evidence records and the screenshots.
5. The example's README: what the author contributed, where the plan was wrong, and which needs are only partly
   tested.

## How it works

```
 requirement (text)
        |
        v
 +--------------------- Claude Code + the odoo-functional skill ---------------------+
 |  reads knowledge/20.0 (decision rules, pitfalls, sources)                        |
 |  inspects the demo DB through ofa (read-only)       ofa lint-plan: every name    |
 |  writes plan.json + plan.md  ------------------->   checked against 20.0 source  |
 |                     REVIEW STOP: the user approves (or asks for changes)         |
 |  ofa freeze -> ofa apply -> writes scenarios -> ofa test -> screenshots (MCP)    |
 +----------------------------------------------------------------------------------+
        |  JSON-2 API, loopback only, demo DBs only        ^ PreToolUse hook checks
        v                                                  | every shell command
 Odoo 20 server (hardened conf)  <-- template DB --> ofa_demo_<name> databases
        |
        v
 runs/<run_id>/: apply.json, test.json, test_history.jsonl, records.json, files/,
                screenshot_targets.json, screenshots/, report.md
```

- **The plan.** `plan.json` is an ordered list of four operation types (`install_modules`, `set_settings`,
  `upsert_record`, `call_method`), each with a rationale and knowledge references; `plan.md` explains them.
  `ofa validate` and `ofa lint-plan` check it before review; `ofa freeze` records the approved hash, and `ofa apply`
  refuses anything else. Format: [docs/plan_format.md](docs/plan_format.md).
- **Scenarios.** JSON step lists that create records, press the buttons a user would press and read fields back.
  Format: [docs/scenario_format.md](docs/scenario_format.md). Each run directory holds what `ofa apply` and
  `ofa test` wrote (operation statuses, scenario results, every earlier test call, the records read back, exported
  files, screenshot targets) and a `report.md` that links them: [docs/run_artifacts.md](docs/run_artifacts.md).
- **Knowledge.** [knowledge/20.0/](knowledge/20.0/INDEX.md): one entry per topic, with sources in the 20.0 code or
  documentation and a list of known 20.0 drifts in [knowledge/README.md](knowledge/README.md). A second skill,
  `odoo-explain`, answers "why" and "when" questions from it without touching Odoo.

Design decisions: [docs/architecture.md](docs/architecture.md).

## How it is kept safe

The machine it runs on can host other Odoo databases on the same Postgres server, so no single control is trusted
alone. Full detail: [docs/guard.md](docs/guard.md).

- **Layer a, the `ofa` client.** A target must be registered by `ofa provision`, be named `ofa_demo_*`, live on
  loopback and carry the marker UUID written when it was created; every client checks this before its first call.
- **Layer b, a PreToolUse hook** shipped with the plugin. It checks every shell command and denies direct `psql`,
  `odoo-bin`, HTTP calls to Odoo and browser navigation off loopback. It acts only from the moment a session uses
  the agent (the `odoo-functional` or `odoo-explain` skill, an `ofa` command or a `Target:` line in a prompt; `help`
  does not count), so your other projects are not affected, and before that moment there is no protection. A guarded
  session stays guarded after `/clear`, `/compact` and forks, and for 30 days after its last use when resumed. See
  [When it acts](docs/guard.md#when-it-acts).
- **Server hardening.** `list_db = False`, `dbfilter = ^ofa_demo_.*$`, `max_cron_threads = 0`; `ofa server start`
  refuses a config without them.
- **Test identities** cannot be administrators: a role a plan gives them is checked before and after writing.
- **The permission mode is not a layer.** Claude Code's permission settings decide what runs without a prompt; the
  guard does not rely on them. The Mexican-localization example's session ran in `auto` mode, and 89 of its 91
  shell commands were not a plain `ofa` command (measured from the session transcript on 2026-10-28; the transcript
  is not kept), so an allow rule on `ofa` matched almost none of them; the hook still checked every one.
- **Known gaps**, all listed in [docs/guard.md](docs/guard.md#known-gaps): the hook is pattern matching, so a
  script written to disk and run, indirect execution (git aliases, make targets) or in-page clicks are not
  inspected; a script that talks to Postgres directly is stopped only by the hook.

## Repeatable means "same frozen plan, same state"

Applying the same frozen plan to a fresh demo database gives the same configuration, and applying it again changes
nothing (every operation `unchanged`). `ofa dump` writes a canonical, id-free JSON of what a plan configured, to
compare two databases. It does **not** mean that the same requirement text gives the same plan: plans are written by
a language model and are reviewed, not regenerated.

## Scope by area

All five examples ran on Odoo 20.0 **Enterprise** (each plan installs at least one Enterprise module, such as the
full Accounting app). Most knowledge entries are Community features (Sales, Purchase, Inventory, invoicing), but no
example has been run end to end on Community.

| Area | Example | What it covers | Limits found |
|---|---|---|---|
| Sales + CRM | [sales_crm_quote_to_cash](examples/sales_crm_quote_to_cash/README.md) | pipeline, campaign quotes, down payments, invoicing methods | line-level quote history is not tracked; no scenario registers a payment |
| Purchase + Inventory | [purchase_inventory_procure_to_pay](examples/purchase_inventory_procure_to_pay/README.md) | approval threshold, vendor prices, replenishment, two-step receipts, lots and FEFO, 3-way matching | the approval threshold is on the taxed total; Odoo proposes the largest quantity break, not the cheapest vendor; 3-way matching flags a bill but does not block payment |
| Accounting | [accounting_invoicing_and_taxes](examples/accounting_invoicing_and_taxes/README.md) | fiscal positions, payment terms with early discount, euro and exchange differences, bank matching, analytics, roles and the monthly close | a mandatory analytic plan is enforced only by the Post button, not by the API; blocking manual entries needs a rule the plan adds |
| Mexican localization | [l10n_mx_cfdi_ready_company](examples/l10n_mx_cfdi_ready_company/README.md) | CFDI 4.0 invoices, payment complements, credit notes, global invoice, cancellation with substitution, fee withholdings, SAT chart of accounts and trial balance XML | **Stamps for real against a third-party test PAC**, so a re-run needs internet and that service; the demo CSDs expire on 2027-01-18 and 2027-05-18 (as shipped in the `l10n_mx_edi` 20.0 demo data, read on 2026-10-26), after which stamping stops; the test PAC's automatic cancellation was intermittent; needs Enterprise |
| Multi-company | [multi_company_holding](examples/multi_company_holding/README.md) | separate companies and a branch, shared data, per-company isolation, a group controller, inter-company orders and bills, group reports with eliminations | a branch-only user cannot create a taxed invoice in the demo template, because of a defect in the Enterprise Mexican localization the template installs (traced on a disposable database, the reproduction is not published; see the example); the group balance sheet keeps inter-company balances |

The SAT files are generated through the trial balance report and read back in scenarios with `save_as` and `check`
(see below).

## What scenarios can do

Beyond creating records, calling buttons and reading fields back, scenarios gained these during the build (the
earlier examples predate some of them, and their READMEs say what they could not test for that reason):

- **`company`**: run a scenario, a step or an evidence read in one company, as a user who picked it.
- **`as`**: run a step as one of three test users that `ofa provision` creates, each with its own API key. A plan
  gives them a role (a buyer, an accountant, a user per company) with its own operations, so a test proves what
  that role can and cannot do. Every other step runs as `ofa`'s own administrator-level user.
- **`expect_error`**: a negative test passes only when Odoo refuses the call with the declared exception class and
  message; a misspelled field or any `ofa` error is a scenario error, never the expected refusal.
- **`save_as` on a call, and `check`**: keep what a method returns (a report's options, an exported file) and
  assert on it, including XML content.

## Examples and what the author did

Each example was run by the author in one interactive session (resumed once, in the Purchase + Inventory example);
its README says in detail what the author contributed and where the skill was wrong. From the Mexican-localization
example on, the author also reviewed plans with a separate Claude Code session before approving them, and each
example's README marks what came from it.

| Example | The author's part |
|---|---|
| [Sales + CRM](examples/sales_crm_quote_to_cash/README.md) | four intake answers (including choosing the Mexican demo company) and the correction that replaced a proposed custom computed field with a standard one |
| [Purchase + Inventory](examples/purchase_inventory_procure_to_pay/README.md) | two intake answers and one approval; no correction |
| [Accounting](examples/accounting_invoicing_and_taxes/README.md) | two intake answers and two approvals; no correction |
| [Mexican localization](examples/l10n_mx_cfdi_ready_company/README.md) | the choice of a custom fiscal-data rule, a change to the Test plan, the choice of a global invoice and two corrections to the plan |
| [Multi-company](examples/multi_company_holding/README.md) | the group controller's design, two changes to the Test plan and the branch decision |

Where a run had to be repeated by the project's maintainer (a fresh database, a newer `ofa`, screenshots), the
example says so and keeps the skill's own run as it was.

## Requirements

- **Your own Odoo 20.0** source checkout and PostgreSQL. The Enterprise addons are needed for the examples and for
  the Mexican localization; their source is never in this repository.
- Python 3.11+ for `ofa` (standard library only).
- Claude Code. Screenshots use the Firefox DevTools MCP server; without it the evidence is the read-back records.

Setup: [docs/setup.md](docs/setup.md). Keeping the knowledge current:
[docs/knowledge_upkeep.md](docs/knowledge_upkeep.md).

## Install as a plugin

```
/plugin marketplace add xmglord/odoo-functional-agent
/plugin install odoo-functional-agent@xmglord
```

Finish [the setup](docs/setup.md) once (your Odoo 20.0, the `ofa` config and the template database), then go to
[Using it](#using-it).

## Using it

The one thing to remember: type `/odoo-functional-agent:odoo-functional` (typing `/odoo` brings it up in the
autocomplete) and paste the requirement in the same message.

```
/odoo-functional-agent:odoo-functional We are a bike shop. Any quote with a discount above 10% needs a sales
manager's approval before it can be confirmed, and every bike must be traceable by serial number from receipt
to delivery.
```

Ask for the skill by name rather than describing the need and waiting for it to start.

To see the flow again and check whether your machine is ready, without changing anything, type
`/odoo-functional-agent:help` or ask "how do I use this plugin?".

### What happens

1. **It checks your setup and starts the local Odoo server.** If the check finds a problem, it shows it and stops.
2. **It creates a demo database** for this requirement. If one with that name exists, it asks whether to reuse or
   reset it.
3. **It may ask up to 3 questions**, only about decisions that change the configuration. Real names and tax ids in
   your text are replaced with fictional ones, and it tells you which.
4. **It stops with the plan and the Test plan.** You read what it will configure and why, which test proves each
   need, and which needs will not be tested.
5. **Nothing is applied until you approve explicitly**, with a message like "approved" or "yes, apply it". A question
   or a comment is not approval, and neither is having said "do everything" earlier. If the plan changes after that,
   it asks again.
6. **It applies the plan, runs the tests and delivers the report**: pass or fail for each need, every difference from
   the Test plan you approved, what has to be done by hand in the Odoo screens, and what it learned about your case
   in business terms.

### What it asks of you, and when

- **Your answers and your approval**, in steps 3 to 5.
- **Firefox, only for screenshots, and it is optional.** After the tests it uses the browser if it is available; if
  not, it asks you to start it and to keep the window visible. Without screenshots, the evidence is the records the
  tests read back.
- **Cleanup, at the end.** The demo database stays so you can look at it. The skill offers to drop it and does so
  only if you say yes.

### What you get, and what you do not

You get a plan proven on a demo database: the requirement, `plan.json`, `plan.md`, the test scenarios and a run
report, all under `plans/<slug>/` in the folder where you started Claude Code.

It never touches a real Odoo. `ofa` works only on the local demo databases it created, so moving the result to a
production system is your decision and your work.

### Asking a question

To understand Odoo rather than change it, use `odoo-explain` the same way:

```
/odoo-functional-agent:odoo-explain when should I use lots instead of serial numbers?
```

It answers from the plugin's knowledge compendium, cites the entries and says so when no entry covers the question.
It never changes Odoo.

## License

MIT. See [LICENSE](LICENSE).
