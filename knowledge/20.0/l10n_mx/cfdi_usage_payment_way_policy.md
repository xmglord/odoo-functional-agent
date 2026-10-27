---
title: CFDI usage, payment way and payment policy (UsoCFDI, FormaPago, MetodoPago)
area: l10n_mx
odoo_version: 20.0
edition: enterprise
source: [enterprise/l10n_mx_edi/models/account_move.py@20.0, enterprise/l10n_mx_edi/models/l10n_mx_edi_document.py@20.0, enterprise/l10n_mx_edi/models/res_partner.py@20.0, enterprise/l10n_mx_edi/models/account_journal.py@20.0, enterprise/l10n_mx_edi/models/l10n_mx_edi_payment_method.py@20.0, enterprise/l10n_mx_edi/models/account_move_line.py@20.0, enterprise/l10n_mx_edi_sale/models/sale_order.py@20.0, enterprise/l10n_mx_edi/wizard/l10n_mx_edi_global_invoice_create.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [l10n_mx_edi, l10n_mx_edi_sale]
models: [account.move, res.partner, account.journal, l10n_mx_edi.payment.method, account.move.line, sale.order, l10n_mx_edi.global_invoice.create]
settings: []
---

## When to use
- Each invoice CFDI carries three codes the customer cares about:
  - **usage** (`UsoCFDI`): what the customer will deduct the invoice as (G01 merchandise, G03 general expenses,
    I04 computer equipment, S01 no fiscal effect...). The customer tells you; store it on the partner when it is
    always the same.
  - **payment policy** (`MetodoPago`): `PUE` (paid in one payment, at or before invoicing) or `PPD` (paid later or
    in installments). PPD invoices require a payment complement for every payment (see the payment complements
    entry).
  - **payment way** (`FormaPago`): how a PUE invoice was paid (01 cash, 03 transfer, 04 credit card...). For PPD
    the CFDI always says `99` (to be defined) and the real way goes on each payment complement.
- If a customer always pays by transfer, set its payment way on the partner (or on the sales journal) so invoices
  never go out without one: the test PAC rejects a PUE invoice without it.

## Configuration
- `account.move` (`enterprise/l10n_mx_edi/models/account_move.py@20.0`):
  - `l10n_mx_edi_usage` (selection `USAGE_SELECTION`): stored compute, editable; for MX invoices the partner's
    `l10n_mx_edi_usage`, else the current value, else `G03`.
  - `l10n_mx_edi_payment_policy` (`PPD`, `PUE`): stored compute, editable. Order: `PUE` for credit notes, an
    explicit value, the partner's `l10n_mx_edi_payment_policy`; otherwise `PPD` when the due date is after the
    invoice date and in a later month, or the payment term has several lines, else `PUE`.
  - `l10n_mx_edi_payment_method_id` (many2one `l10n_mx_edi.payment.method`, label "Payment Way"): stored compute,
    editable; for invoices the partner's, else the current value, else the journal's
    `l10n_mx_edi_payment_method_id`; payments fall back to "Transferencia" (`l10n_mx_edi.payment_method_transferencia`).
  - `l10n_mx_edi_cfdi_to_public`: send to "público en general" (see the fiscal data entry).
- CFDI values (`_add_payment_policy_cfdi_values`, `l10n_mx_edi_document.py@20.0`): PPD writes `MetodoPago=PPD`,
  `FormaPago=99`; PUE writes `MetodoPago=PUE` and the payment way's `code`.
- `l10n_mx_edi.payment.method` records (`code`, `name`, `active`): xmlids `l10n_mx_edi.payment_method_efectivo`
  (01), `payment_method_cheque` (02), `payment_method_transferencia` (03), `payment_method_tarjeta_de_credito` (04),
  `payment_method_tarjeta_debito` (28), `payment_method_anticipos` (30), and others (live).
- Defaults per customer on `res.partner`: `l10n_mx_edi_usage`, `l10n_mx_edi_payment_method_id`,
  `l10n_mx_edi_payment_policy`; per journal: `account.journal.l10n_mx_edi_payment_method_id`.
- Lines: `account.move.line.l10n_mx_edi_tax_object` (`ObjetoImp`, `01` ... `08`), computed from the line taxes.
- Sales orders (`l10n_mx_edi_sale`, auto-installed with `sale`): `sale.order.l10n_mx_edi_usage`,
  `l10n_mx_edi_payment_method_id`, `l10n_mx_edi_payment_policy`, `l10n_mx_edi_cfdi_to_public`, copied to the
  invoice by `_prepare_invoice`.
- Every invoice needs products whose `unspsc_code_id` is set (`ClaveProdServ`); the line UoM's `unspsc_code_id`
  gives `ClaveUnidad` (Units = `H87`, live).

## How to verify
- On the invoice before posting: `l10n_mx_edi_usage`, `l10n_mx_edi_payment_policy`, `l10n_mx_edi_payment_method_id`,
  `l10n_mx_edi_is_cfdi_needed = True` (live in `l10n_mx_invoice_stamp`: `G03`, `PUE`, payment way 03).
- After stamping, `l10n_mx_edi_cfdi_state = 'sent'`; the stored XML (`l10n_mx_edi_cfdi_attachment_id`, read its
  `raw`) shows `UsoCFDI`, `MetodoPago`, `FormaPago`.

## Pitfalls
- **Payment way is effectively required for PUE.** The field help says "Leave empty if unknown and the XML will
  show 'Unidentified'", but an empty payment way was rejected by the Quadrum test PAC with `CFDI40223` ("los
  atributos FormaPago y MetodoPago se vuelven requeridos") on 2026-10-26. The demo partners and journals have none.
  There is no "99 Por definir" record to pick either.
- The PPD rule compares calendar months: a 30-day term on an invoice dated the 1st stays in the same month and gives
  PUE. If the business sells on credit, set `PPD` on the partner or the invoice instead of relying on the term.
- A product without `unspsc_code_id` blocks the CFDI ("You need to define an 'UNSPSC Product Category' on the
  following products").
- `ir.attachment` has no `datas` field in 20.0: read the CFDI XML through `raw`.
- Usage `P01` is no longer valid in CFDI 4.0; it is replaced by `S01` when sent.

## Alternatives
- Global invoice for sales to the public: `l10n_mx_edi.global_invoice.create` (from
  `account.move.l10n_mx_edi_action_create_global_invoice`) groups "público en general" invoices of a period into one
  CFDI instead of stamping each.
- Payment way on the journal instead of the partner when the payment way depends on how money comes in (a card
  terminal journal).

## Mexico notes
Mexico note for the sales invoicing policy and payment terms entries; listed under "Cross-references" in the
l10n_mx index.
