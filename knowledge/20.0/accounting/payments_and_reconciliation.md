---
title: Payments and reconciliation basics
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/account_payment.py@20.0, odoo/addons/account/wizard/account_payment_register.py@20.0, odoo/addons/account/models/account_move.py@20.0, odoo/addons/account/models/account_move_line.py@20.0, odoo/addons/account/models/account_payment_method.py@20.0, odoo/addons/account/models/account_partial_reconcile.py@20.0, odoo/addons/account/models/account_full_reconcile.py@20.0, enterprise/accountant/models/account_move.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account]
models: [account.payment, account.payment.register, account.payment.method.line, account.move, account.move.line, account.partial.reconcile, account.full.reconcile]
settings: []
---

## When to use
- If the requirement says "register that the customer paid" or "pay this vendor bill", the flow is the
  register-payment wizard on the posted invoice/bill: it creates an `account.payment` and reconciles it with the
  invoice's receivable/payable line, so the invoice shows as paid.
- If money arrives without an invoice reference (a customer prepays, or pays several invoices at once), record a
  standalone payment and then **reconcile** its receivable line with the invoice's (the "outstanding credits"
  widget on the invoice does exactly that).
- If payments must wait for the bank statement before counting as cleared, give the bank journal's payment methods
  an **outstanding account** (`payment_account_id`): the payment then posts to "Outstanding Receipts/Payments" and
  the bank statement line later clears that account.

## Configuration
- Payment: `account.payment` with `payment_type` (`inbound`, `outbound`), `partner_type` (`customer`, `supplier`),
  `partner_id`, `amount`, `date`, `journal_id`, `payment_method_line_id`, `memo`; computed `outstanding_account_id`
  (= the method line's `payment_account_id`), `destination_account_id` (partner's receivable/payable), `move_id`
  (its journal entry), `state` (`draft`, `paid`, `reconciled`, `canceled`, `rejected`), `is_reconciled`,
  `is_matched` (matched with a bank statement), `invoice_ids`, `reconciled_invoice_ids`. `action_post` sets `state`
  to `paid`.
- Register-payment wizard: `account.move.action_register_payment` (posted invoices only) returns an
  `ir.actions.act_window` on `account.payment.register` with `target: new`, no `res_id`, and context
  `active_model = 'account.move.line'`, `active_ids` = the invoice's lines. The wizard (`line_ids`, `amount`,
  `payment_date`, `journal_id`, `payment_method_line_id`, `communication`, `group_payment`, `installments_mode`,
  `payment_difference_handling` `open`/`reconcile`, `writeoff_account_id`) is confirmed with
  `action_create_payments`. Over `ofa`, a `call` of `action_register_payment` with
  `"wizards": {"account.payment.register": "action_create_payments"}` creates the wizard from that context and
  confirms it (C5).
- Manual reconciliation: `account.move.js_assign_outstanding_line(line_id)` on the invoice reconciles one
  outstanding line (e.g. a payment's receivable line) with the invoice's open lines on the same account;
  `account.move.line.reconcile()` reconciles a set of lines together; `remove_move_reconcile()` undoes it.
- Results: `account.partial.reconcile` (`debit_move_id`, `credit_move_id`, `amount`, `full_reconcile_id`,
  `exchange_move_id`) per matched pair; `account.full.reconcile` when the lines are fully settled. On the lines:
  `account.move.line.reconciled`, `amount_residual`, `matching_number`, `full_reconcile_id`.
- Invoice status: `account.move.amount_residual`, `payment_state` (`not_paid`, `in_payment`, `paid`, `partial`,
  `reversed`, `blocked`, `invoicing_legacy`), `matched_payment_ids`.

## How to verify
- After the wizard: the invoice's `amount_residual == 0` and `payment_state` is `paid` (Invoicing only) or
  `in_payment` (full Accounting, until the bank statement matches); one `account.payment` whose `invoice_ids`
  contains the invoice, `state` in `paid` / `reconciled`, `move_id` set when the method line has an outstanding
  account.
- After a manual reconciliation: the invoice's receivable line (`display_type = 'payment_term'`) and the payment's
  receivable line both have `reconciled = true` and the same `matching_number`, and an `account.partial.reconcile`
  links them.
- Partial payment: `payment_state == 'partial'` and `amount_residual` equals the open amount.

## Pitfalls
- **Two apps, two behaviours.** In 20.0 the full "Accounting" app is the Enterprise module `accountant`; the module
  `account_accountant` is "Invoicing" (Enterprise). `accountant` overrides `_get_invoice_in_payment_state` to return
  `in_payment` (`enterprise/accountant/models/account_move.py@20.0`). Without it, `account.payment.create` forces
  an outstanding account on every payment, so payments always post a journal entry and paid invoices become `paid`.
  With it, a payment whose method line has no `payment_account_id` creates **no journal entry**: the invoice goes
  to `in_payment` while its `amount_residual` stays open until a bank statement line is reconciled.
- So whether a scenario sees `paid` or `in_payment`, and whether `amount_residual` drops to 0 at payment time,
  depends on `accountant` and on `payment_account_id`. Configure the bank journal's method lines explicitly (the
  `accounting` fixture plan sets the inbound manual line to Outstanding Receipts) and assert
  `payment_state in [paid, in_payment]`.
- `action_register_payment` refuses drafts ("You can only register payment for posted journal entries.") and
  miscellaneous entries.
- The register-payment wizard needs the `active_model`/`active_ids` context: creating `account.payment.register`
  with no `line_ids` and no such context raises `UserError` ("The register payment wizard should only be called on
  account.move or account.move.line records.", `default_get`). Go through `action_register_payment` (with `ofa`
  wizard following).
- `account.payment.state` `paid` only means "confirmed". It becomes `reconciled` when its liquidity line is settled,
  and also as soon as every invoice it pays is `paid` while its outstanding account is not of type `asset_cash`
  (`_compute_state`). Live (scenario `accounting_invoice_payment_reconcile`, no `accountant`): the wizard payment
  read `state = 'reconciled'`, `outstanding_account_id` = Outstanding Receipts, a `move_id` set, and the invoice
  `payment_state = 'paid'`, `amount_residual = 0`; the standalone 100 payment on a 230 invoice read `paid` before
  and `is_reconciled = true` after `js_assign_outstanding_line`, with the invoice `partial` and 130 open.
- Write-offs and exchange differences: a payment that differs from the residual stays open
  (`payment_difference_handling = 'open'`) unless `reconcile` with a `writeoff_account_id` is chosen.
- Matching bank statement lines with payments or invoices is done in the bank reconciliation screen of the
  Enterprise apps; this entry did not check an RPC path for it, so plans should leave it to the user.

## Alternatives
- Batch payments (`account_batch_payment`) to deposit several customer checks or send one bank transfer file.
- Online payment providers (`account_payment`) so customers pay invoices from the portal; the payment is created and
  reconciled by the provider flow.
- Reconciliation models (`account.reconcile.model`) to propose matches on bank statement lines automatically.

## Mexico notes
A payment that settles a Mexican invoice paid in installments (PPD) is expected to produce a payment complement CFDI
in `l10n_mx_edi`; this entry did not verify that flow. See the `l10n_mx` area.
