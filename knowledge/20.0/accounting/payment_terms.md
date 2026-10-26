---
title: Payment terms, due dates and installments
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/account_payment_term.py@20.0, odoo/addons/account/models/account_move.py@20.0, odoo/addons/account/models/account_move_line.py@20.0, odoo/addons/account/models/partner.py@20.0, odoo/addons/account/wizard/account_payment_register.py@20.0, odoo/addons/account/data/account_data.xml@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account]
models: [account.payment.term, account.payment.term.line, account.move, account.move.line, res.partner, account.payment.register]
settings: []
---

## When to use
- If customers or vendors pay on credit (30 days, end of month, 30% now and 70% in 60 days), give them a payment
  term, because the term is what produces the **due dates** on the receivable/payable lines: aged balances, follow-up
  reminders and the "overdue" filters all read those dates.
- If one invoice is paid in several installments, use one term line per installment; each becomes its own
  receivable line with its own due date, and payments can target the next installment only.
- If the business grants a discount for paying early (2% within 10 days), use a term with `early_discount`; the
  discount is then proposed automatically when the payment is registered in time.
- This entry is the accounting side. How a term reaches quotations and orders is in
  `knowledge/20.0/sales_crm/payment_terms_on_quotes.md`.

## Configuration
- `account.payment.term`: `name`, `active`, `company_id` (empty = shared), `sequence`, `note`, `display_on_invoice`
  ("Show installment dates"), `line_ids`, and early payment discount fields `early_discount`, `discount_percentage`
  (default 2.0), `discount_days` (default 10), `early_pay_discount_computation` (`included` = tax reduced on early
  payment, `excluded` = never, `mixed` = always, upon invoice).
- `account.payment.term.line`: `value` (`percent` / `fixed`), `value_amount` (0-100 for percent), `delay_type`
  (`days_after`, `days_after_end_of_month`, `days_after_end_of_next_month`, `days_end_of_month_on_the`), `nb_days`,
  `days_next_month` (day of the next month for `days_end_of_month_on_the`).
- Standard records in `account_data.xml@20.0`, e.g. `account.account_payment_term_immediate`,
  `account.account_payment_term_15days`, `account.account_payment_term_21days`,
  `account.account_payment_term_30days`, `account.account_payment_term_30days_early_discount`,
  `account.account_payment_term_30_days_end_month_the_10` (all in the data file; all but the first also read on the
  live template DB).
- Partner defaults (company dependent): `res.partner.property_payment_term_id` (customer) and
  `property_supplier_payment_term_id` (vendor).
- On the invoice: `account.move.invoice_payment_term_id`; the receivable/payable lines (`display_type =
  'payment_term'`) get `date_maturity` per term line, and `invoice_date_due` is the latest of them
  (`_compute_invoice_date_due`). Without a term, it keeps the value already set, else the invoice date.
- Paying installments: the register-payment wizard `account.payment.register.installments_mode` (`next`, `overdue`,
  `before_date`, `full`) chooses which installment amount it proposes.

## How to verify
- Term lines: read `value`, `value_amount`, `delay_type`, `nb_days` on each `line_ids` record; percent lines sum to
  100.
- Partner: `property_payment_term_id` (customer) or `property_supplier_payment_term_id` (vendor) equals the term,
  read with the company in context.
- Posted invoice: `invoice_payment_term_id` is the term; `account.move.line` records with `move_id = invoice` and
  `display_type = 'payment_term'` are one per installment with the expected `date_maturity`; `invoice_date_due`
  equals the last one. Live (scenario `accounting_invoice_payment_reconcile`): an invoice with
  `account.account_payment_term_30days` posted on 2026-10-26 read one `payment_term` line and
  `invoice_date_due = 2026-11-26`.

## Pitfalls
- A term must have percent lines summing to exactly 100 ("The Payment Term must have at least one percent line and
  the sum of the percent must be 100%."). `fixed` lines come on top of that; a term made only of fixed lines is
  rejected.
- Early payment discount only works on a term with a **single 100% line** ("The Early Payment Discount
  functionality can only be used with payment terms using a single 100% line."), and needs a positive
  `discount_percentage` and `discount_days`.
- A term referenced by documents cannot be deleted (`UserError` "Those payment terms are quite popular and can't be
  deleted..."); archive it.
- The partner's term only fills new documents. Changing it does not touch posted invoices; their due dates are
  fixed in the receivable lines.
- Overdue follow-up runs from the scheduled action `account_followup.ir_cron_follow_up` (Enterprise,
  `enterprise/account_followup/data/cron.xml@20.0`). On demo targets `max_cron_threads = 0`, so nothing is sent or
  advanced on its own; a scenario must not wait for it.

## Alternatives
- Down payments or prepayment (sales area) when the money is wanted before delivery rather than later.
- A manual `invoice_date_due` on invoices without a term, for one-off arrangements.

## Mexico notes
The term matters for CFDI: an invoice paid at once versus in installments is expected to drive the payment method
(PUE vs PPD) and payment complements in `l10n_mx_edi`. This entry did not verify that logic; see the `l10n_mx` area.
