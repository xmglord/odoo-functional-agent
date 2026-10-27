---
title: Company and partner fiscal data (RFC, fiscal regime, fiscal ZIP)
area: l10n_mx
odoo_version: 20.0
edition: enterprise
source: [enterprise/l10n_mx_edi/models/res_company.py@20.0, enterprise/l10n_mx_edi/models/res_partner.py@20.0, enterprise/l10n_mx_edi/models/res_config_settings.py@20.0, enterprise/l10n_mx_edi/models/l10n_mx_edi_document.py@20.0, enterprise/l10n_mx_edi/models/account_move.py@20.0, odoo/odoo/addons/base/models/res_partner.py@20.0, enterprise/l10n_mx_edi_extended/models/res_partner.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [l10n_mx_edi, l10n_mx_edi_extended]
models: [res.company, res.partner, res.config.settings, account.move]
settings: [l10n_mx_edi_fiscal_regime]
---

## When to use
- Every CFDI names the issuer and the receiver by RFC, fiscal regime and fiscal ZIP code, and the SAT rejects a
  CFDI whose receiver data does not match its registry. Configure them before the first invoice:
  - the company: RFC in `vat`, fiscal regime in `l10n_mx_edi_fiscal_regime`, ZIP of its fiscal address in `zip`
    (it becomes `LugarExpedicion`);
  - each customer that asks for a nominative invoice: RFC in `vat`, `country_id = base.mx`, `zip` and
    `l10n_mx_edi_fiscal_regime` exactly as on the customer's "constancia de situación fiscal".
- If the customer does not give an RFC (retail, walk-in customers), leave `vat` empty: the invoice goes to "público
  en general" (generic RFC `XAXX010101000`, regime 616, usage S01). If the customer is foreign, the CFDI uses the
  generic foreign RFC `XEXX010101000`.

## Configuration
- `res.company.l10n_mx_edi_fiscal_regime` (selection `FISCAL_REGIMES_SELECTION`, codes `601` ... `630`, e.g. `601`
  General de Ley Personas Morales, `612` Personas Físicas con Actividades Empresariales y Profesionales, `626`
  RESICO). Settings field `l10n_mx_edi_fiscal_regime` (related, `res.config.settings`).
- `res.partner` (`enterprise/l10n_mx_edi/models/res_partner.py@20.0`):
  - `l10n_mx_edi_fiscal_regime`: stored compute, editable. Empty without country, `616` (Sin obligaciones
    fiscales) for a foreign country, `601` by default for Mexico.
  - `l10n_mx_edi_partner_address_complete`: computed, **not stored**, true when `country_id`, `zip` and `vat` are
    all set.
  - `l10n_mx_edi_usage`, `l10n_mx_edi_payment_method_id`, `l10n_mx_edi_payment_policy`: defaults for the
    partner's invoices (see the usage and payment way entry).
  - `l10n_mx_edi_ieps_breakdown`, `l10n_mx_edi_addenda_ids`.
- `l10n_mx_edi_extended` adds `l10n_mx_edi_curp` (natural persons), `l10n_mx_edi_colony`, `l10n_mx_edi_colony_code`,
  `l10n_mx_edi_locality`, `l10n_mx_edi_locality_id` and `l10n_mx_edi_external_trade_type`
  (`enterprise/l10n_mx_edi_extended/models/res_partner.py@20.0`).
- RFC format check: `res.partner.check_vat_mx` in base (`odoo/odoo/addons/base/models/res_partner.py@20.0`): 3 or
  4 letters (Ñ and & allowed), a valid YYMMDD date, 3 characters of homoclave.
- Receiver logic (`_add_customer_cfdi_values`, `enterprise/l10n_mx_edi/models/l10n_mx_edi_document.py@20.0`): a
  Mexican customer with RFC is named with `vat`, `zip` (`DomicilioFiscalReceptor`) and its regime (`616` if empty);
  without RFC, or with `l10n_mx_edi_cfdi_to_public` on the invoice, the receiver is generic.
- Invoice: `l10n_mx_edi_cfdi_to_public` is computed true when the partner is not Mexican or its address is
  incomplete (no country, ZIP or RFC) (`_compute_l10n_mx_edi_cfdi_to_public`, `account_move.py@20.0`).
- Branches: the RFC used is the one of the first parent company with `partner_id.vat` (the "root company"), and the
  regime falls back to the root company's (`_get_company_cfdi_values`, `_add_certificate_cfdi_values`).

## How to verify
- Company: `vat`, `zip`, `l10n_mx_edi_fiscal_regime` (live, demo company 4: `IVD920810GU2`, regime `601`).
- Partner: `vat`, `zip`, `country_id`, `l10n_mx_edi_fiscal_regime` (live, demo partner
  `l10n_mx_edi.demo_partner_sapien_1`: `XIA190128J61`, regime `624`).
- Draft invoice: `l10n_mx_edi_cfdi_to_public = False` for a customer with complete data (checked live in
  `l10n_mx_invoice_stamp`), true for a customer without RFC.

## Pitfalls
- `l10n_mx_edi_partner_address_complete` is not stored: it cannot be used in a search domain ("Field has no SQL
  representation"). Search on `vat`, `zip` and `country_id` instead.
- An empty partner regime is sent as `616` for a named Mexican receiver, which the SAT rejects for most legal
  entities: set the regime explicitly from the customer's tax certificate.
- `l10n_mx_edi_fiscal_regime` on a partner recomputes when the country changes: changing a Mexican customer to a
  foreign country silently resets it to `616`.
- A customer without ZIP blocks sending (`_check_move_constraints`: "CFDI not set to Public: The partner specified
  does not have recognized country and/or ZIP code set.") unless the invoice is marked to public.
- The format check accepts any RFC-shaped value; it does not ask the SAT whether the RFC exists. The PAC does.
- Use only fictional or SAT test data in demo databases: the demo companies' RFCs `IVD920810GU2` and
  `ZUÑ920208KL4` are SAT test RFCs bound to the shipped demo CSDs.

## Alternatives
- Retail sales without customer RFC: invoice "público en general" one by one, or group them into a global invoice
  (`l10n_mx_edi.global_invoice.create`, see the usage and payment way entry).
- A branch (`parent_id`) that invoices under the parent's RFC instead of its own company with its own RFC and CSD.

## Mexico notes
This is the Mexico note for partner and company data in the sales and purchase areas; listed in the l10n_mx index
under "Cross-references".
