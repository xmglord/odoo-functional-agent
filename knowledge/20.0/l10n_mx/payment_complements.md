---
title: Payment complements (CFDI de pago) for PPD invoices
area: l10n_mx
odoo_version: 20.0
edition: enterprise
source: [enterprise/l10n_mx_edi/models/account_move.py@20.0, enterprise/l10n_mx_edi/models/account_payment.py@20.0, enterprise/l10n_mx_edi/models/account_payment_register.py@20.0, enterprise/l10n_mx_edi/models/l10n_mx_edi_document.py@20.0, enterprise/l10n_mx_edi/views/account_move_view.xml@20.0, enterprise/l10n_mx_edi/wizard/l10n_mx_edi_register_factoring.py@20.0, odoo/addons/account/models/account_payment.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [l10n_mx_edi, account_accountant]
models: [account.move, account.payment, account.payment.register, account.payment.method.line, l10n_mx_edi.document]
settings: []
---

## When to use
- If the company sells on credit or in installments, its invoices are `PPD`, and every payment received for them
  must be reported to the SAT in a payment complement (a CFDI of type "P", "Recepción de pagos") that names the
  paid invoices by UUID, the amount and the payment way. Configure the payment journals so payments post journal
  entries and plan the "Update Payments" step after each reconciliation.
- If every invoice is paid at once before or when it is issued, keep them `PUE`: their payments are recorded with a
  `payment_sent_pue` document and nothing is stamped.

## Configuration
- Prerequisites: the invoice is stamped (`l10n_mx_edi_cfdi_state = 'sent'`, its UUID is referenced) and has
  `l10n_mx_edi_payment_policy = 'PPD'` (see the usage and payment way entry).
- **The payment needs a journal entry.** With the full Accounting app (`account_accountant`, a dependency of
  `l10n_mx_edi`), a payment whose payment method line has no `payment_account_id` gets no `move_id`
  (`account.payment.create`, `odoo/addons/account/models/account_payment.py@20.0`), so there is nothing to
  reconcile and no complement. Set `account.payment.method.line.payment_account_id` (Outstanding Receipts, e.g.
  `account.4_account_journal_payment_debit_account_id`) on the bank journal's inbound methods.
- Payment way: `account.payment.l10n_mx_edi_payment_method_id` (related to its move, computed from the partner,
  then the journal, then "Transferencia"); `account.payment.register.l10n_mx_edi_payment_method_id` on the
  register-payment wizard.
- Sending: the invoice button "Update Payments" calls `account.move.l10n_mx_edi_cfdi_invoice_try_update_payments`
  (visible when `l10n_mx_edi_update_payments_needed`). For each reconciled payment dated today or earlier it either
  records a PUE document (no PPD invoice) or stamps the complement with the company's PAC
  (`l10n_mx_edi_cfdi_invoice_try_update_payment`). No automatic send on posting or reconciling was found in the
  source; plan the button (or the call) as a step.
- Results on the payment (related to its move): `l10n_mx_edi_cfdi_state = 'sent'`, `l10n_mx_edi_cfdi_uuid`,
  `l10n_mx_edi_cfdi_attachment_id`, `l10n_mx_edi_payment_document_ids`; the `l10n_mx_edi.document` row has `state =
  'payment_sent'`, `move_id` = the payment's move and the paid invoices in `invoice_ids`. Failed sends are
  `payment_sent_failed` and are retried from the document (`action_retry`).
- Bank statement lines reconciled with a PPD invoice count as payments too (`_l10n_mx_edi_is_cfdi_payment` checks
  `origin_payment_id` or `statement_line_id`).

## How to verify
- Invoice: `payment_state = 'partial'` or `paid`, `amount_residual` as expected.
- Payment: `state = 'paid'`, `move_id` set, `reconciled_invoice_ids` contains the invoice, `l10n_mx_edi_cfdi_state
  = 'sent'`, `l10n_mx_edi_cfdi_uuid` set.
- `l10n_mx_edi.document` with `move_id.origin_payment_id` = the payment and `state = 'payment_sent'`.
- Scenario `scenarios/20.0/l10n_mx/l10n_mx_ppd_payment_complement.json`: PPD invoice 5,800.00 stamped, payment of
  2,900.00 by transfer, complement stamped with the Quadrum test PAC (live, 2026-10-27).

## Pitfalls
- A PPD invoice paid with a payment that has no journal entry stays `in_payment` and never produces a complement;
  nothing warns about it.
- A payment dated in the future is skipped by "Update Payments" until its date.
- The complement takes the payment way of the payment, not of the invoice; a PPD invoice's own CFDI always says
  `FormaPago=99`.
- Like invoices, complements need network access to the PAC and a valid CSD; in a demo database the demo CSDs
  expire (2027-01-18 for company 5, 2027-05-18 for company 4).
- Unreconciling a payment after its complement was stamped leaves a stamped complement that must be cancelled; the
  button handles removing unsent documents only.

## Alternatives
- Factoring: `l10n_mx_edi.register.factoring` with the company's `l10n_mx_edi_factoring_account_id` when invoices
  are sold to a factoring company (new in 20.0, not exercised here).
- Selling `PUE` (payment before invoicing, e.g. down payments) avoids complements altogether.

## Mexico notes
Mexico note for [payments_and_reconciliation.md](../accounting/payments_and_reconciliation.md) and
[payment_terms.md](../accounting/payment_terms.md).
