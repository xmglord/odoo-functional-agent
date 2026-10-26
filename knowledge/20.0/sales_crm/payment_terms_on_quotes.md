---
title: Payment terms on quotations and sales orders
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/finance/accounting/customer_invoices/payment_terms.html, odoo/addons/account/models/account_payment_term.py@20.0, odoo/addons/account/models/partner.py@20.0, odoo/addons/account/data/account_data.xml@20.0, odoo/addons/sale/models/sale_order.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [account, sale]
models: [account.payment.term, account.payment.term.line, res.partner, sale.order, account.move]
settings: []
---

## When to use
- If a customer has agreed credit conditions (30 days, 50% now and 50% in 60 days, end of month), set the payment
  term on the customer (`property_payment_term_id`), because every new quotation for that customer then carries it
  and the invoice created from the order inherits it, so due dates and follow-ups are right without manual edits.
- If the business offers a discount for early payment (2% if paid within 10 days), use a payment term with
  `early_discount`.
- If the terms are negotiated per deal, change `payment_term_id` on the quotation itself; it overrides the customer
  default for that order only.
- Payment terms are an accounting object: see the accounting area for how due dates and reconciliation work. This
  entry covers only how they reach sales documents.

## Configuration
- `account.payment.term`: `name`, `active`, `company_id`, `sequence`, `note`, `display_on_invoice` ("Show
  installment dates"), `line_ids`, early discount fields `early_discount`, `discount_percentage`,
  `discount_days`, `early_pay_discount_computation`.
- `account.payment.term.line`: `payment_id`, `value` (`percent` / `fixed`), `value_amount` (for percent, 0-100),
  `delay_type` (`days_after`, `days_after_end_of_month`, `days_after_end_of_next_month`,
  `days_end_of_month_on_the`), `nb_days`, `days_next_month`. The percent lines must sum to 100.
- Standard records: `account.account_payment_term_immediate`, `account.account_payment_term_30days`,
  `account.account_payment_term_advance_60days`, and others in `odoo/addons/account/data/account_data.xml@20.0`.
- Customer default: `res.partner.property_payment_term_id` (company dependent).
- On the order: `sale.order.payment_term_id` is computed from `partner_id.property_payment_term_id` (in the order's
  company), stored and writable. The invoice gets it as `account.move.invoice_payment_term_id` when created from the
  order.

## How to verify
- Term exists: `account.payment.term` with the expected `line_ids` (read `value`, `value_amount`, `delay_type`,
  `nb_days` on each line).
- Customer: `res.partner.property_payment_term_id` equals the term (read with the right company in context).
- Quotation: a new `sale.order` for that customer has `payment_term_id` equal to the term.
- Invoice: the `account.move` created from the order has `invoice_payment_term_id` equal to the order's term, and
  `invoice_date_due` follows its lines once posted.

## Pitfalls
- `property_payment_term_id` is company dependent: setting it in one company does not set it in another; in a
  multi-company database read and write it with the company in context.
- `payment_term_id` is recomputed when the order's customer changes, so a manual term is lost if the customer is
  changed afterwards.
- `value_amount` is 0-100 for percent lines; a term whose percent lines do not sum to 100 is rejected
  ("The Payment Term must have at least one percent line and the sum of the percent must be 100%.").
- Do not confuse payment terms (when the invoice is due) with online prepayment (paying the quotation to confirm it)
  or down payments (a separate advance invoice).
- Payment terms with a `company_id` are not selectable on orders of other companies.

## Alternatives
- Online prepayment on the quotation when the business wants the money before confirmation.
- Down payments when part of the price is invoiced after confirmation but before delivery.
- Customer credit limits (accounting settings) when the concern is exposure, not due dates.

## Mexico notes
For a Mexican company the due date that the payment term produces is expected to drive the CFDI payment policy
(PUE or PPD); this entry did not check that in the `l10n_mx_edi` source. See the `l10n_mx` area before choosing
terms for a Mexican company.
