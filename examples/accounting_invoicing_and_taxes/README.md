# Example 3: Accounting, invoicing to monthly close

A fictional design and software consultancy, Lumen Ridge Studios, wants invoicing, payments and the monthly close
in Odoo 20: taxes chosen from the customer, project and retainer payment terms with an early payment discount, euro
customers with automatic exchange differences, two bank accounts, profitability per project and department, and a
billing clerk who cannot touch what only the accountant may. The author wrote the requirement
([requirement.md](requirement.md)) and ran the `odoo-functional` skill on it in one interactive Claude Code session
(2026-10-28, 00:11 to 00:33 UTC), on fresh demo databases provisioned by the skill.

What to look at, in order:

1. [requirement.md](requirement.md): the business requirement, six numbered needs.
2. [plan.md](plan.md): the decisions, the **Test identities** (a billing clerk and an accountant), the **Test plan**
   and "Not covered".
3. [plan.json](plan.json): the 30 operations; [plan.approved](plan.approved) holds the hash of the approved version.
4. [scenarios/](scenarios/): the fifteen functional tests the skill wrote, in their final form.
5. The runs below, each with a `report.md`.

## What changed in the skill and in `ofa` since example 2

Used in this session:

- **Test identities** (`daafd15`). `ofa provision` creates three test users with their own API keys; a plan gives
  one a role with an op, and a scenario step runs `as` that role, so Odoo applies that user's rights. Here the plan
  makes `ofa_user_1` a billing clerk and `ofa_user_2` an accountant. Before this, every test ran as the `ofa` bot,
  an administrator, and no "the clerk cannot..." need could be tested (example 2's approval need was left untested
  for that reason).
- **Rerun a fixed scenario in full** (`ab17e7f`). After fixing scenarios that failed through its own mistakes, the
  skill reran all fifteen on a new database `t25_2` with the same frozen plan, instead of a read-only recheck.
- **Runs keep every scenario's results** (`f73bd3c`).

Added after this session, because of what it showed, and used only by the maintainer re-run:

- **`expect_error`** (`a54b6c3`, `2aa514c`). A step passes only when Odoo refuses the call with the declared
  exception class and message text. A misspelled field or any `ofa` error is a scenario error, never the expected
  refusal. During the session the skill had no such step, so it wrote its four negative tests as scenarios whose
  expected result is **fail**, and said so in the Test plan the author approved.
- **`match` finds archived records** (`c0cac12`). See the first apply below.
- Two corrections to the knowledge compendium (`1ae876f`, `fd9e8cb`): the mandatory-analytic and rate-date
  findings below.

## Runs

| Run | Who | What happened |
|---|---|---|
| [`20261028T002429Z_t25`](runs/20261028T002429Z_t25/apply.json) | the skill, first approval | Apply only. It stopped at `op_030_currency_eur`: the template's EUR is archived, the op's `match` named it by `$ref`, and the search left archived records out, so the op tried to create a second EUR and failed ("Missing required field 'Currency'"). The skill changed the `match` to include archived records, asked for approval again and got it. |
| [`20261028T002607Z_t25`](runs/20261028T002607Z_t25/report.md) | the skill, discarded by it | Apply of the re-approved plan, then eleven scenarios: two failed through mistakes in the scenarios (EUR, profitability), two "negatives" failed as designed, and the negative for mandatory analytics **passed**: the clerk posted an invoice with no project or department (see need 5). |
| [`20261028T003107Z_t25_2`](runs/20261028T003107Z_t25_2/report.md) | the skill, its final run | New database `t25_2`, same frozen plan: 23 `created`, 6 `adopted`, 1 `updated`, no `pre_state`. Fifteen scenarios: 11 pass and the four negatives fail with the refusal they were written to hit. No screenshots (see below). |
| [`20261028T005158Z_t25r`](runs/20261028T005158Z_t25r/report.md) | **re-run by the project's maintainer session, not by the skill** | New database `t25r`, the same approved plan unchanged: the same apply statuses. The same fifteen scenarios in the same order, with the four negatives converted to `expect_error` ([scenarios_maintainer_rerun/](scenarios_maintainer_rerun/)): all fifteen pass and `ofa test` exits 0. Twelve screenshots, one per target, taken by the maintainer with the skill's procedure and checked against their records. |

Not in this folder: a maintainer second apply of the plan on `t25_2` (all 30 `unchanged`), an apply-only run.

The conversion of the negatives changed only how the refusal is checked: each refused step got
`expect_error` with the class and text Odoo returned in the skill's run. In `lr_neg_clerk_lock_date` the refused
step created the lock-date wizard and saved it for a second step that confirmed it; a refused create leaves nothing
to confirm, so that second step and the `save_as` were dropped. No step after a refusal reads back that nothing
changed; the skill now writes that read-back, but these scenarios predate the rule.

## What the author contributed

No manual UI work and no functional correction: the plan the skill wrote is the plan that ran.

1. **The requirement.**
2. **Two answers at intake**, both the skill's recommendation:
   - Projects billed 30% at signature and 70% on delivery: a sales order with a 30% down payment invoice and a final
     invoice due in 30 days, rather than two invoices typed by hand.
   - What a "project" is for profitability: an analytic account in a "Projects" plan, next to a "Departments" plan,
     rather than installing the Project app.
   - Free comment: "Sin comentarios", which the skill had labelled with its defaults: demo company 1 (USD, the
     generic chart's 15% sales tax) standing in for the studio, and a Global Lock Date (reopenable) for the close.
3. **Two approvals**, "aprobado" each time: the plan, and the plan with `op_030`'s fixed `match`.

Agent time: about 18 minutes and 293,953 new tokens, not counting the author's 4 minutes at the two review stops.

Permission mode: not measured. The session transcript was deleted at cleanup, before the T26 audit showed
that the mode, not the launch command's `--allowedTools`, decided which commands ran without a prompt.

## Requirement against tests

| Need | Proved by | Gap |
|---|---|---|
| 1. Domestic customers get the standard sales tax automatically | `lr_tax_domestic_vs_export`: a clerk's invoice to a US customer gets the Domestic position and 15% | The demo's 15% stands in for the studio's real rate |
| 1. Customers abroad: no tax, and the invoice says why | `lr_tax_domestic_vs_export`: a German customer gets the Foreign Trade position, 0% Exports and the "Export of services" note | |
| 2. Projects 30% at signature, 70% on delivery due in 30 days | `lr_project_down_payment`: down payment invoice of 3,000, final invoice of 7,000 due in 30 days | |
| 2. Retainers due in 15 days; 2% within 10 days with the tax reduced in proportion | `lr_retainer_early_discount`: due date +15; a bank line of 1,127 pays the 1,150 invoice, with 20.00 to the discount account and 3.00 of tax reversed | |
| 3. EUR invoices and payments, exchange difference booked automatically | `lr_eur_exchange_difference`: an EUR invoice from the EUR pricelist, paid on the euro bank, residual 0, and an exchange entry | Invoices typed by hand for a European customer do not default to EUR (in "Not covered") |
| 4. Two bank accounts; one transfer for several invoices; partial payments | `lr_bank_multi_invoice_partial`: one bank line of 2,000 closes one invoice and leaves exactly 300 on the other | Statement lines are created by the scenario; bank import and synchronization are not covered |
| 4. A partial refund is a credit note tied to the invoice | `lr_partial_refund_credit_note`: an `out_refund` of 230 whose `reversed_entry_id` is the invoice | |
| 5. Every invoice and bill assigned to a project and a department | `lr_unassigned_analytic_flagged`: a line without a distribution has `has_invalid_analytics` true | **Met in the UI only, and the test is weaker than planned.** The plan makes both analytic plans mandatory, but Odoo enforces a mandatory plan only when the Post or Confirm button sends `validate_analytic=True`; posting through the API, an import or an automation goes through without project or department. The planned test (the clerk's post is refused) passed the post instead. The skill replaced it with a check of the flag the button reads, which proves the line is marked, not that posting is blocked. The compendium said otherwise and is now fixed (`1ae876f`). |
| 5. Revenue, costs and margin by project and department | `lr_profitability`: Client Portal's analytic balance 3,500 (5,000 revenue, 1,500 costs) and the lines per department | The Analytic Report itself is not read; the test reads analytic lines |
| 6. The clerk invoices and records bills | the clerk's invoices and bills in the scenarios above | **Sending invoices by email is not tested**: no outgoing mail server on demo databases |
| 6. The clerk cannot post manual entries, change taxes or touch closed periods | `lr_neg_clerk_manual_entry`, `lr_neg_clerk_change_tax`, `lr_neg_clerk_lock_date`: refused with `AccessError` | In the skill's run these are "expected fail"; as passes only in the maintainer re-run. **Manual entries are blocked by a rule the plan adds, not by standard configuration** (`op_280_no_manual_entries`, Decision 7): the Invoicing group has full create/write/delete on `account.move` and Odoo only hides the menu, so the plan adds a global `ir.access` restriction that lets users without `account.group_account_user` touch only moves that are not `entry`. Its costs, stated in the plan: the clerk cannot register payments either (a payment's journal entry is an `entry`), nor run any flow that writes a miscellaneous entry as the clerk; and a Bookkeeper (`account.group_account_user`) passes the restriction, so "only the accountant" holds as "only accounting users". Taxes and lock dates are blocked by standard rights. |
| 6. Only the accountant posts adjustments and closes the month | `lr_accountant_adjustment`, `lr_close_month`: the accountant posts a manual entry and sets the lock date to 2026-08-31 | **The close moves a late invoice to today, not to the first open day.** An invoice dated 2026-08-20, posted after August is locked, gets the accounting date of the posting day (2026-10-28), not 2026-09-01. The test only requires it to leave August. |
| 6. Nobody, the accountant included, changes a closed month without reopening it | `lr_neg_accountant_edit_closed`: the accountant's reset to draft is refused with `UserError` ("You cannot add/modify entries prior to and inclusive of: Global Lock Date"); `lr_reopen_month`: a one-hour lock exception for the accountant, then an invoice dated in August posts with that date | |

Two other findings of the session, both checked in the 20.0 source:

- **A currency rate applies from the day after its date** in Odoo 20 (`name < date`; 19.0 used `<=`). The skill's
  EUR scenario first dated its rates on the invoice and payment days, and the invoice took the old demo rate. It
  moved the rates a day earlier. Now a known 20.0 drift in the compendium (`fd9e8cb`).
- **Scenarios sharing an analytic account interfere.** The EUR scenario first posted to Client Portal and changed
  the balance `lr_profitability` checks; the skill moved it to another project.

## Screenshots

The skill's runs have none. Its only login attempt, on `t25_2`, landed on the database selector: the browser still
held a session for a database the maintainer had used for example 2's screenshots and then dropped (the server log
shows Odoo finding that database unusable and redirecting). The procedure stopped there, as it says to. It now
retries the login once in that case and logs out at the end (`b61537e`); the maintainer reproduced the problem on a
throwaway database and took the screenshots below with the new procedure.

All from the maintainer re-run:

- Taxes from the customer: [domestic
  invoice](runs/20261028T005158Z_t25r/screenshots/lr_tax_domestic_vs_export_domestic_invoice.png) (15%) and [export
  invoice](runs/20261028T005158Z_t25r/screenshots/lr_tax_domestic_vs_export_export_invoice.png) (0% Exports; the
  fiscal position and its note are on the "Other Info" tab, proved by the assertions).
- 30/70: [down payment
  invoice](runs/20261028T005158Z_t25r/screenshots/lr_project_down_payment_down_payment_invoice.png) (3,000) and [final
  invoice](runs/20261028T005158Z_t25r/screenshots/lr_project_down_payment_final_invoice.png) (10,000 less the 3,000
  down payment).
- [Retainer invoice](runs/20261028T005158Z_t25r/screenshots/lr_retainer_early_discount_retainer_invoice.png):
  "Retainer: 15 days, 2% within 10 days", paid.
- [EUR invoice](runs/20261028T005158Z_t25r/screenshots/lr_eur_exchange_difference_eur_invoice.png): in EUR at 0.90,
  paid.
- One transfer, two invoices: [invoice
  1](runs/20261028T005158Z_t25r/screenshots/lr_bank_multi_invoice_partial_invoice_1.png) partial and [invoice
  2](runs/20261028T005158Z_t25r/screenshots/lr_bank_multi_invoice_partial_invoice_2.png) paid.
- [Credit note](runs/20261028T005158Z_t25r/screenshots/lr_partial_refund_credit_note_credit_note.png): "Reversal of:
  INV/2026/00018", 200 + 30 tax, paid.
- [Subcontractor bill](runs/20261028T005158Z_t25r/screenshots/lr_profitability_subcontractor_bill.png) with project
  Client Portal and department Engineering.
- [Draft invoice with an unassigned
  line](runs/20261028T005158Z_t25r/screenshots/lr_unassigned_analytic_flagged_draft_invoice_missing_analytic.png): one
  line has no project or department; the form does not show `has_invalid_analytics`.
- [Late August invoice](runs/20261028T005158Z_t25r/screenshots/lr_close_month_late_august_invoice.png): invoice date
  Aug 20, accounting date Oct 28, the day it was posted.

In every screenshot the company switcher shows the admin's current company (the Mexican one); that is the
browser's display, and every record belongs to company 1 (USD).

## Verdict on the third v1 area

"On a fresh demo database, from a written requirement covering at least one v1 area, the agent produces a
reviewable plan, applies it and runs functional tests that pass, without manual UI work by the author."

Met for Accounting, with the gaps above: fresh databases, a written requirement, a plan that validated and passed
the lint gate (one plan.md name left for review), an apply and a second apply that changed nothing, and no UI work or functional correction by the
author. The skill's own final run has four negative tests reported as fail by design; they pass as `expect_error`
steps in the maintainer re-run. Need 5's "every invoice is assigned" holds only in the web client.
