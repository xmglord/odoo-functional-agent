# Example 5: Multi-company holding

A fictional US group, Ridgeline, wants its holding, two operating companies and a branch of one of them in a single
Odoo 20 database: separate legal companies with their own books, shared products, customers and vendors with
per-company terms, staff who see only their company, a group controller who sees all of them but does not post in
one, inter-company purchase orders and invoices mirrored automatically, a monthly management fee, and group
reports that do not count inter-company sales twice. The author wrote the requirement
([requirement.md](requirement.md)) and ran the `odoo-functional` skill on it in one interactive Claude Code session
(2026-10-28, 17:23 to 17:57 UTC).

What to look at, in order:

1. [requirement.md](requirement.md): six numbered needs.
2. [plan.md](plan.md): the decisions, the **Test identities** (Foods staff, branch staff, the group controller), the
   **Test plan** and "Not covered".
3. [plan.json](plan.json): the 26 operations; [plan.approved](plan.approved) holds the hash of the approved version.
4. [scenarios/](scenarios/): the eight functional tests the skill wrote.
5. The runs below, each with a `report.md`.

## What changed in the skill and in `ofa` since example 4

- **`save_as` on `call` and the `check` step** (`d604db7`) existed during this session, but only in
  `docs/scenario_format.md`: SKILL.md did not mention them, so the skill's first Test plan left group reporting as
  "read in the UI" until the author pointed to the scenario format at the review stop. Then the skill used them for
  the group P&L. SKILL.md now teaches them (`d3f53a0`).
- **Screenshot procedure** (`38dc7ac`): no fixed window size, log-out with clicks.
- The session was launched without `--allowedTools`; see "How the session ran".

## Runs

| Run | Who | What happened |
|---|---|---|
| [`20261028T174209Z_t27`](runs/20261028T174209Z_t27/report.md) | the skill, first database | Apply: 20 `created`, 4 `adopted`, 2 `updated`, no `pre_state`. First test call: `t27_branch` failed because branch staff could not create a taxed invoice (the finding below); `t27_haul_flow` failed on a mistake in the scenario (a malformed `$set` in the invoicing wizard) and `t27_isolation` on the refusal text it expected ('write' instead of 'read'); `t27_group_reporting` was in error through another scenario mistake (`file` used on a number). The skill fixed the scenarios and reran them in full; it isolated the branch problem with throwaway diagnostic scenarios and asked the author. |
| [`20261028T175349Z_t27_2`](runs/20261028T175349Z_t27_2/report.md) | the skill, second database | After the second approval: `t27_branch` passed with the approved workaround; `t27_group_reporting` failed on wrong line positions in the report (the plan had assumed `lines.1` and `lines.8`). |
| [`20261028T175520Z_t27_3`](runs/20261028T175520Z_t27_3/report.md) | the skill, its final run | A third database, from scratch: the same apply statuses and all eight scenarios pass. No screenshots. |

All three apply the same plan.json (sha256 `c1949c0c…`): both plan changes were to plan.md (decisions and tests),
not to operations. A maintainer second apply on `t27_3` changed nothing (an apply-only run, not in this folder).
After the final run the skill corrected one description in plan.md (Decision 9, the line positions, marked
"Corrected after the run"); the Test plan keeps the approved text.

## What the author contributed

No manual UI work. The author's part, with what the author's review session suggested marked as such:

1. **The requirement.**
2. **Two answers at intake.**
   - Group controller: Odoo's access groups apply to all of a user's companies, so "an accountant in every company
     except Logistics" does not exist as standard. The skill recommended read-only everywhere; the author first
     chose it.
   - Eliminations: Odoo 20 has no consolidation module; selecting several companies in a report only adds them up.
     The author chose a separate Ridgeline Eliminations company, the skill's recommendation.
3. **The controller redesigned** (suggested by the review session). Read-only collides with the requirement, which
   only forbids posting in Logistics, and someone has to post the eliminations. The author asked for a Bookkeeper
   in every company plus a marker group and a global `ir.access` restriction on journal entries that leaves
   Logistics out. The skill checked it was possible and asked how to name the companies in the domain; the author
   chose an **allow-list** (the restriction fails closed: the controller may create, change or delete entries only
   in Holdings, Foods, the Foods branch and Eliminations).
4. **Two changes at the first review stop** (both suggested by the review session): test group reporting with
   `get_options`, `save_as` and `check` instead of "read in the UI"; and check whether `account.move.auto_post =
   'monthly'` covers the monthly fee before reaching for Subscriptions. Both went into the plan, plan.json
   unchanged.
5. **The branch decision.** When the branch finding appeared, the skill offered workarounds; the author chose that
   branch invoices are issued by an accountant who has Foods and the branch, working in the branch, while branch
   staff stay in the branch only. The author also asked that the final report describe the finding with minimal
   reproduction steps, separating what was measured from what was deduced.
6. **Two approvals**, "aprobado" each time: after the first review stop's changes, and after the branch change.

Agent time: about 22 minutes and 410,699 new tokens, not counting the author's time at the stops.

## Requirement against tests

| Need | Proved by | Gap |
|---|---|---|
| 1. Holdings, Foods and Logistics are separate legal companies with own chart, journals, bank, numbering | `t27_structure`: root companies with the US chart and their own sales and bank journals | Real bank account numbers are not configured |
| 1. The Foods branch: Foods' tax ID, identifiable invoices, own stock | `t27_branch`: the branch has Foods' tax ID and no bank journal; its invoices get the branch journal (`RVINV`); branch staff see the branch warehouse and not Foods' | **Branch staff cannot issue taxed invoices themselves** in this database (finding below: a defect of `l10n_mx_edi`, installed by the demo template); in the plan an accountant with Foods and the branch issues them |
| 2. Shared products, customers and vendors; vendor terms, prices and taxes per company | `t27_shared_data`: shared records found from every company; vendor terms 30 days in Foods and 45 in Logistics; Foods' pricelist price 26.50 vs 30.00 in Logistics, no cross-company taxes | Sharing does not block a typed duplicate customer |
| 3. Staff only in their company; branch staff only in the branch | `t27_isolation`: Foods staff do not find Logistics' or the branch's documents, bank or warehouse, and a write on a Logistics invoice is refused (`expect_error`); branch staff do not find Foods' orders | Logistics staff have no test user (only three exist); isolation is symmetric |
| 3. The controller sees and switches between every company, runs multi-company reports, does not post in Logistics | `t27_controller`: finds every company's invoices; posts in Eliminations and Foods; creating an entry in Logistics and posting a Logistics invoice are refused (`expect_error`); `t27_group_reporting`: the controller's report options cover the five companies | The restriction rests on a marker group and a global `ir.access` rule the plan adds, not on standard groups |
| 4. Foods' haul PO → Logistics SO; Logistics' invoice → Foods draft bill | `t27_haul_flow`: a draft SO in Logistics linked to the PO, and a draft vendor bill in Foods linked to the invoice | |
| 5. Monthly management fee → draft bills | `t27_management_fee`: Holdings' fee invoices to Foods (12,000) and Logistics (9,000) create draft bills; an invoice with `auto_post = 'monthly'` produces next month's copy | **The cron that posts the copy on its date is Not tested** (a test cannot move the clock); the first invoice of each series is created by hand |
| 6. P&L and balance sheet per company and for the group, without inter-company double counting | `t27_group_reporting`, as the controller through `check` steps: Holdings' P&L revenue 21,000; the group P&L without Eliminations shows revenue and cost of sales of 21,850 each, and 0 / 0 / 0 once the elimination entry is posted | **The group balance sheet does not eliminate inter-company receivables and payables**: the elimination entry nets revenue against cost only. The balance sheet is only checked to run and return lines; its figures are not asserted |

Differences from the approved Test plan, as the skill reported them: the refusal in `t27_isolation` came back as
"doesn't have 'read' access to", not 'write' (the Foods user cannot even read the Logistics invoice, so the read
check refuses first); the report line positions were corrected; the controller's refusal in Logistics comes from
the journal items, so the restriction also covers `account.move.line`.

## Finding: a branch-only user cannot create a taxed invoice

Measured in the session: a user whose only company is the branch gets `AccessError: Access to unauthorized or invalid
companies.` when creating a customer invoice whose line has a tax. Without a tax the invoice is created, a sales
order with taxes is created, and a user who also has Foods creates the same invoice in the branch.

The skill deduced a cause in `account_reports` (a company switch to the root without superuser rights in
`account_return.py`) and said it had not verified it. **The maintainer reproduced it on a throwaway database with
a traceback, and the cause is elsewhere**: `l10n_mx_edi` (Enterprise), installed in the demo template for its
Mexican companies, hooks into every invoice line's tax computation whatever the company's country
(`account.tax._l10n_mx_edi_is_generic_local_tax`, `l10n_mx_edi/models/account_tax.py`) and there switches to the
tax's company without superuser rights. A branch uses its root company's taxes, so the switch goes to a company the
branch-only user is not allowed. With that one method changed to switch with superuser rights, the same user
creates the invoice. 19.0's `l10n_mx_edi` has no such method.

**So the branch decision rests on a defect that depends on what the template has installed**, not on how branches
work in Odoo 20: a US database without the Mexican localization would most likely not have this limitation (not
tested). The author's choice, branch invoices issued by an accountant with Foods and the branch, was made while the
cause was unknown. plan.md stays as the author approved it; its "Not covered" still points to `account_reports`,
which this section corrects. The defect is reported to Odoo through Enterprise support, not in this repository.

## How the session ran

Permission mode: **`auto`** (all 53 permission-mode records of its transcript), launched without `--allowedTools`.
The plugin's guard hook ran on every command.

## Screenshots

The skill took none: the `admin` user it logs in with did not have the Ridgeline companies (6 to 10), so their
records would not open. After the run, **the maintainer gave `admin` those five companies on `t27_3`** (admin is no
test identity and every scenario had already run), took the five screenshots with the skill's procedure at the
window's size, 1161 x 632, and logged out.

- [Branch invoice](runs/20261028T175520Z_t27_3/screenshots/t27_branch_branch_invoice.png): `RVINV/2026/00001` in the "Riverside Branch Invoices"
  journal, with a 6% tax, issued by the accountant who has Foods and the branch.
- [Elimination entry](runs/20261028T175520Z_t27_3/screenshots/t27_group_reporting_elimination_entry.png): 21,850 of product sales against cost of
  goods sold in Ridgeline Eliminations.
- [Haul sales order in Logistics](runs/20261028T175520Z_t27_3/screenshots/t27_haul_flow_haul_so.png), generated from Foods' purchase order (`P00017`),
  and [the draft bill in Foods](runs/20261028T175520Z_t27_3/screenshots/t27_haul_flow_haul_bill.png) generated from Logistics' invoice.
- [Management fee invoice to Foods](runs/20261028T175520Z_t27_3/screenshots/t27_management_fee_fee_invoice_foods.png): 12,000 from Holdings.

The company switcher shows the admin's current company (San Francisco); the records belong to the Ridgeline
companies.

## Verdict on the fifth v1 area

"On a fresh demo database, from a written requirement covering at least one v1 area, the agent produces a
reviewable plan, applies it and runs functional tests that pass, without manual UI work by the author."

Met for multi-company, with the gaps above: the final run on a fresh database applies the plan and passes all
eight scenarios, a second apply changes nothing, and the author did no UI work. Two parts of the requirement are
held by configuration the plan adds rather than by standard groups (the controller's restriction) or by a
workaround (branch invoices issued by an accountant with Foods, forced by a defect of the Mexican localization
the demo template carries), and the group balance sheet keeps inter-company balances.
