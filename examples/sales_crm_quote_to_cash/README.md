# Example 1: Sales + CRM, quote to cash

A fictional advertising company, Vantage Venue Media, wants its campaign sales cycle in Odoo 20, from the
opportunity to the customer's payment. The author wrote the requirement ([requirement.md](requirement.md)) and ran
the `odoo-functional` skill on it in one interactive Claude Code session (2026-10-27, 16:33 to 16:57 UTC), on a
fresh demo database `t21` provisioned by the skill.

What to look at, in order:

1. [requirement.md](requirement.md): the business requirement, six numbered needs.
2. [plan.md](plan.md): the decisions, each with its business reason, what Odoo does, the pre-state, alternatives,
   pitfalls and sources, plus "Custom fields created, for your evaluation" and "Not covered by this plan".
3. [plan.json](plan.json): the 37 operations `ofa` applied; [plan.approved](plan.approved) holds the hash of the
   approved version.
4. [scenarios/](scenarios/): the four functional tests the skill wrote.
5. The three runs below, each with a `report.md`.

## Runs

| Run | Who | What happened |
|---|---|---|
| [`20261027T164705Z_t21`](runs/20261027T164705Z_t21/report.md) | the skill, plan v1 | First apply on the fresh database: 31 `created`, 4 `adopted` (existing pipeline stages renamed), 1 `updated` (settings), 1 `unchanged` with `pre_state` (`op_010_install_apps`: the apps were already in the template, so that op proves nothing). Two scenarios failed (see "What the author contributed"). |
| [`20261027T165302Z_t21`](runs/20261027T165302Z_t21/report.md) | the skill, plan v2 | Apply of the re-approved plan: 2 `updated` (the order form and list views), 35 `unchanged`. All four scenarios pass. Ten screenshots taken by the skill through the browser and checked against their records. |
| [`20261027T171415Z_t21`](runs/20261027T171415Z_t21/report.md) | **re-run by the project's maintainer session, not by the skill** | Same plan v2 and database. After `ofa` gained a scenario `company` key, the only change to the four scenarios was a top-level `"company": {"$ref": "base.demo_company_mx"}`; no step or expectation changed. All four pass. |

Why the third run exists: the plan works in the Mexican demo company, but `ofa` used to read everything in its bot
user's default company (San Francisco). The v2 evidence therefore shows the customer's `total_due` as `0.0`, while
the same customer owes 133,980 MXN in the Mexican company. The skill confirmed this in the web client by switching
company ([screenshot](runs/20261027T165302Z_t21/screenshots/vantage_campaign_down_payment_50_customer_balance_mx.png)).
In the re-run, `records.json` reads `total_due` = 133980.0.

Not in this folder: the skill's own idempotency check (a second apply of v1 right after the first, all 37
`unchanged`) and a later maintainer re-apply of v2 (all `unchanged`), which wrote apply-only runs.

The fails of v1 are not in the v1 run's `test.json`: at that time each `ofa test` into a run rewrote it, and the
skill's partial re-run replaced it. They are recorded here from the session transcript. `ofa` now keeps every
invocation in `test_history.jsonl`.

## What the author contributed

The success criterion asks for no manual UI work by the author, and there was none: the author never configured
anything in Odoo's interface. But the author did more than approve, and that is part of the result.

1. **The requirement.**
2. **Four answers at intake**, to the skill's questions:
   - Custom fields: the skill asked whether the plan may create `x_` fields for line dates, customer type and
     billing method, which have no standard field. The author chose "yes, `x_` fields", the skill's recommendation.
   - Quotation history: Odoo tracks order-level changes but not line-level ones. The author chose "standard
     tracking and document the gap", the skill's recommendation.
   - Company: the requirement names no country. The skill recommended the main demo company (San Francisco, USD,
     no CFDI). **The author chose the Mexican demo company instead** (MXN, VAT 16%).
   - Free comment: "document which custom fields were made, so they can be evaluated as necessary or not". The
     plan's "Custom fields created, for your evaluation" section answers it.
3. **Two approvals**, both the message "approved": one for v1 and one for v2.
4. **The correction that produced v2.** In v1 the order's "pending" amount was `amount_to_invoice` ("Un-invoiced
   Balance"). Two scenarios failed on it:
   - `vantage_campaign_down_payment_50`, step `s120`: `amount_to_invoice of id 25: expected eq 66990.0, got 133980.0`
   - `vantage_campaign_partial_milestones`, step `s100`: `amount_to_invoice of id 26: expected eq 11600.0, got 29000.0`

   That field ignores down payments. **The skill recommended a new computed `x_` field with Python code stored in
   the database.** The author answered that standard Odoo must show the 50% and that it had to be another field or
   a missing setting. It was another field: `amount_unpaid` ("Amount Remaining"). v2 only swaps it in the two views,
   with no code. Without that answer the plan would have shipped custom code.
5. **Opening the browser.** The browser for screenshots was not running when the skill reached that step; the
   author opened it and said so.

A third v1 fail was the skill's own scenario mistake (`mail.message.tracking_value_ids` does not exist in 20.0); the
skill fixed the search without changing the expectation.

## Requirement against tests

| Need | Proved by | Gap |
|---|---|---|
| 1. Opportunity with a brief (media, venue, dates, amount) and documents | `vantage_opportunity_to_won`: amount, attachment, stages, won | **The brief's properties are written but no step reads them back**; only a screenshot shows them |
| 1. Customer type, five pipeline stages | `x_customer_type` asserted in all four scenarios; stages through `stage_id` | |
| 2. One campaign code on quotation, order and invoices | the `CMP/` sequence; `invoice_origin` asserted on every invoice | |
| 3. One line per medium, venue and period; prices before VAT; line discount | `vantage_campaign_down_payment_50` step `s040`: subtotal, `x_start_date`/`x_end_date`, taxes | The line dates do not reach invoice lines or the PDF (in "Not covered") |
| 4. What changed, who and when | `vantage_quote_history_full_on_po`: the chatter logs subtotal, total and billing method changes | **Line-level history (which price, discount or date changed) is not logged**; need 4 is only partly met, a gap the author accepted at intake |
| 5. Three invoicing methods; customer PO number on the order and invoices | one scenario per method; `client_order_ref` and the invoices' `ref` asserted | `x_billing_method` is a label and drives nothing; there is no reminder to invoice the second 50% before the campaign starts |
| 6. On the order: invoiced and pending | `amount_invoiced` and `amount_unpaid` at each step (133,980 → 66,990 → 0) | |
| 6. On the customer: what they owe and since when | step `s180` counts two open receivable lines with due dates | **The customer's total owed is not asserted**: it is only in the evidence (`total_due`, correct in the re-run) |
| "to the customer's payment" | | **No scenario registers a payment** |

Also outside the plan: the invoices are posted in the Mexican company but not stamped as CFDI (the "Payment Way"
required for stamping is never set), and the CFDI for down payments is not configured.

## Verdict on the first success criterion

"On a fresh demo database, from a written requirement covering at least one v1 area, the agent produces a
reviewable plan, applies it and runs functional tests that pass, without manual UI work by the author."

Met, with the gaps above: fresh database, a written Sales + CRM requirement, a plan that validated and passed the
lint gate, an apply and a second apply that changed nothing, four passing scenarios, no UI work by the author. The
plan was right only after the author's `amount_unpaid` correction, and four needs are proved partly or not at all.
