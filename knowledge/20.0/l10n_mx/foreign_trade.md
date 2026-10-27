---
title: Foreign trade complement (Comercio Exterior) for exports
area: l10n_mx
odoo_version: 20.0
edition: enterprise
source: [enterprise/l10n_mx_edi_extended/__manifest__.py@20.0, enterprise/l10n_mx_edi_extended/models/account_move.py@20.0, enterprise/l10n_mx_edi_extended/models/res_partner.py@20.0, enterprise/l10n_mx_edi_extended/models/res_company.py@20.0, enterprise/l10n_mx_edi_extended/models/product_template.py@20.0, enterprise/l10n_mx_edi_extended/models/uom_uom.py@20.0, enterprise/l10n_mx_edi_extended/models/account_journal.py@20.0, enterprise/l10n_mx_edi/models/l10n_mx_edi_document.py@20.0, odoo/addons/l10n_mx/data/template/account.tax-mx.csv@20.0]
verified_on: 2026-10-27
verified_against: [source]
modules: [l10n_mx_edi_extended, l10n_mx_edi]
models: [account.move, account.move.line, res.partner, res.company, product.template, uom.uom, l10n_mx_edi.tariff.fraction, l10n_mx_edi.res.locality, account.journal]
settings: [l10n_mx_edi_num_exporter]
---

## When to use
- If a Mexican company exports goods definitively (merchandise leaves the country and is sold abroad), the SAT
  requires the "Comercio Exterior" complement on the invoice CFDI, with tariff fractions, customs units, the USD
  exchange rate and the full addresses of issuer and receiver. Install `l10n_mx_edi_extended` and mark the foreign
  customer as "Definitive".
- If it only sells services abroad, or goods that do not cross customs, leave the external trade type at "Does not
  apply" (`01`): the invoice is a normal CFDI to the generic foreign RFC, with IVA 0% from the "Foreign Customer"
  fiscal position.
- The same module also covers first-hand sales of imported goods (customs number, "pedimento", on the line).

## Configuration
- Module: `l10n_mx_edi_extended` ("EDI for Mexico (Advanced Features)", Enterprise, depends on `l10n_mx_edi`, not
  auto-installed; not installed in the demo template).
- Partner: `res.partner.l10n_mx_edi_external_trade_type` (`01` Does not apply (default), `02` Definitive, `03`
  Temporary, `04` Definitive without alienation), plus address detail `l10n_mx_edi_colony`, `l10n_mx_edi_colony_code`,
  `l10n_mx_edi_locality`, `l10n_mx_edi_locality_id` (`l10n_mx_edi.res.locality`), `city_id` with
  `res.city.l10n_mx_edi_code`, and `l10n_mx_edi_curp` for natural persons.
- Invoice: `account.move.l10n_mx_edi_external_trade_type` (computed from the partner, editable, required) and the
  computed `l10n_mx_edi_external_trade` (true for `02`, or `04` with a zero total); `invoice_incoterm_id` (its
  `code` becomes the Incoterm); `l10n_mx_edi_cer_source` (certificate of origin number, optional).
- Invoice lines: `l10n_mx_edi_customs_number` (pedimento, format `15  48  3009  0001234`, checked by a constraint),
  `l10n_mx_edi_umt_aduana_id`, `l10n_mx_edi_qty_umt`, `l10n_mx_edi_price_unit_umt`.
- Products: `product.template.l10n_mx_edi_tariff_fraction_id` (`l10n_mx_edi.tariff.fraction`, SAT catalog with
  `code`, `name`, `uom_code`) and `l10n_mx_edi_umt_aduana_id` (customs unit, a `uom.uom` whose
  `l10n_mx_edi_code_aduana` is set). When product and line UoM share the customs code, the customs quantity is the
  line quantity; with customs code `01` (kilograms) it is `weight × quantity`.
- Company: `l10n_mx_edi_num_exporter` (reliable exporter number, sent only to EU customers; also a settings field),
  address codes `l10n_mx_edi_colony_code`, `l10n_mx_edi_locality_id`.
- Journal: `account.journal.l10n_mx_address_issued_id` (issue address when it differs from the company's).
- The CFDI receiver is `XEXX010101000` for a foreign customer, with its tax id in `NumRegIdTrib` and its country in
  `ResidenciaFiscal` (`_add_customer_cfdi_values`, `l10n_mx_edi_document.py@20.0`; complement in
  `l10n_mx_edi_extended/models/account_move.py@20.0`).

## How to verify
- Partner: `l10n_mx_edi_external_trade_type = '02'`, country, `zip`, `state_id`, `vat` (its foreign tax id).
- Draft invoice: `l10n_mx_edi_external_trade_type = '02'`, `l10n_mx_edi_external_trade = True`,
  `invoice_incoterm_id` set, lines with products that have `l10n_mx_edi_tariff_fraction_id` and
  `l10n_mx_edi_umt_aduana_id`, and `l10n_mx_edi_qty_umt` > 0.
- After stamping: `l10n_mx_edi_cfdi_state = 'sent'`; the XML (`raw` of `l10n_mx_edi_cfdi_attachment_id`) contains the
  `cce20:ComercioExterior` node. Not exercised live for this entry: the module is not in the template and no test
  stamp with the complement was attempted.

## Pitfalls
- The external trade type comes from the partner when the partner is set; changing the partner later recomputes
  it. Set it on the partner, not only on one invoice.
- The complement needs a USD rate for the invoice date (`tipo_cambio_usd`, from `res.currency` rates), also on MXN
  invoices: keep USD rates up to date.
- Mexican issuer address fields are sent as SAT codes (colony code, locality, city code, state code); free text is
  only accepted for foreign addresses.
- Installing `l10n_mx_edi_extended` also pulls `l10n_mx_edi_stock` (delivery guide, "Carta Porte") through its
  `auto_install` when `fleet`, `stock_delivery` and `web_map` are installed; check the module list before
  installing in a database with Inventory.

## Alternatives
- Exports of services: no complement, IVA 0% through the "Foreign Customer" fiscal position.
- Temporary exports (`03`) for goods that will return.

## Mexico notes
Mexico note for the export fiscal position flow in [fiscal_positions.md](../accounting/fiscal_positions.md).
