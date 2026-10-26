# Accounting scenarios fixture: export fiscal position and outstanding receipts

- Requirement: [requirement.md](requirement.md)
- Target edition: community (every op uses the `account` module; the demo template is enterprise)
- Areas: accounting
- Scenarios it supports: `scenarios/20.0/accounting/accounting_invoice_payment_reconcile.json`,
  `scenarios/20.0/accounting/accounting_fiscal_position_export.json`

## Summary
The demo main company ("My Company (San Francisco)", USD, generic chart) already has its chart, a 15% sales tax
(`account.1_sale_tax_template`), a bank journal (`account.1_bank`) and an Outstanding Receipts account
(`account.1_account_journal_payment_debit_account_id`). The plan adds what the two flows need and what the template
does not prove by itself: a dedicated export fiscal position with a 0% tax mapped on the tax side (the 20.0 way), a
customer abroad that carries that position, and an outstanding account on the bank journal's inbound manual payment
method so that every customer payment posts a journal entry.

## Decision 1: Invoicing module
- Ops: [op_010_install_invoicing]
- `account` is installed in the template, so the first apply reports this op `unchanged` with `pre_state: true`: it
  proves nothing about the plan and is kept only to state the dependency.

## Decision 2: Payments post to Outstanding Receipts
- Ops: [op_020_bank_inbound_outstanding]
- On the template every payment method line of the bank journal has `payment_account_id = False`. Without the full
  Accounting app (`accountant`, not installed) Odoo forces an outstanding account anyway; with it, such a payment
  creates no journal entry and the invoice stays open in `in_payment`. Setting the account explicitly makes the
  payment scenario behave the same in both cases. The record is adopted by `match` (journal, inbound, code
  `manual`); the template DB has exactly one such line.
- The `account.1_...` xmlids are those of company 1; this fixture targets the demo main company only.

## Decision 3: Export fiscal position with the 20.0 tax-side mapping
- Ops: [op_030_export_fiscal_position], [op_040_export_sale_tax], [op_050_export_customer]
- The template already has a "Foreign Trade" position with a "0% Exports" tax. A scenario built on it would pass
  without this plan (S2 finding F1), so the plan creates its own position "OFA Export (outside the US)" and its own
  tax "OFA 0% Export".
- The mapping is on the tax: `fiscal_position_ids` = the new position and `original_tax_ids` = the domestic 15%
  sales tax. The domestic tax belongs to the "Domestic" position, so without this mapping it would be dropped (no
  tax at all) on export invoices, not kept.
- The position is not `auto_apply`: "Foreign Trade" (`auto_apply`, no country, sequence 20) would compete for every
  foreign partner. It is set on the customer instead (`property_account_position_id`, company dependent, written
  with the op's company), which always wins over auto-detection.
- The customer is fictional ("OFA Export Customer", country Canada) and carries no tax id or address.

## Not covered
- Bank statement import and matching the payment with the statement (bank reconciliation screen, Enterprise).
- Exchange rates and foreign-currency invoices: the export customer is invoiced in USD.
