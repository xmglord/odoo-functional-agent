---
title: Fiscal positions and the 20.0 tax-side mapping
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/partner.py@20.0, odoo/addons/account/models/account_tax.py@20.0, odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/account_move.py@20.0, odoo/addons/account/models/account_move_line.py@20.0, odoo/addons/account/views/account_tax_views.xml@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account]
models: [account.fiscal.position, account.fiscal.position.account, account.tax, res.partner, res.company, account.move, account.move.line]
settings: []
---

## When to use
- If some customers or vendors must be taxed differently from the domestic default (exports at 0%, intra-EU
  reverse charge, a tax-exempt customer, a different state rate), use a **fiscal position**: it swaps the product's
  taxes (and optionally its income/expense accounts) on the documents of those partners, so products keep one tax
  setup.
- If the rule depends on where the partner is (country, country group, state, zip range, "has a tax id"), set
  `auto_apply` with those criteria, because Odoo then picks the position by itself on every new document.
- If it depends on a decision about one partner (a certificate of exemption), set the position on the partner
  (`property_account_position_id`); a position set on the partner always wins over auto-detection.

## Configuration
- `account.fiscal.position`: `name`, `company_id` (required, read-only, current company by default), `sequence`,
  `active`, `auto_apply`, `vat_required`, `country_id`, `country_group_id`, `state_ids`, `zip_from` / `zip_to`,
  `foreign_vat`, `note` (legal mention printed on invoices), `account_ids` (account mapping,
  `account.fiscal.position.account`: `account_src_id` → `account_dest_id`), computed `is_domestic`.
- **Tax mapping lives on the tax (20.0).** The fiscal position form has no tax mapping lines. Instead each
  replacement tax carries:
  - `account.tax.fiscal_position_ids`: the positions the tax belongs to (inverse:
    `account.fiscal.position.tax_ids`, same relation table);
  - `account.tax.original_tax_ids` ("Replaces"): the domestic taxes it replaces under those positions (domain:
    same `type_tax_use`, `is_domestic = True`); inverse `replacing_tax_ids` (read-only).
  - The position's `tax_map` (computed JSON) is `{original tax id: [replacement ids]}` built from
    `tax_ids.original_tax_ids`.
- Mapping rule (`account.fiscal.position.map_tax`): a tax found in `tax_map` is replaced; a tax not in the map is
  kept **only if it has no `fiscal_position_ids` or includes this position**; otherwise it is dropped.
- Domestic position: `res.company.domestic_fiscal_position_id` (computed: the company's position whose country is
  the company country, lowest `sequence`). Chart templates in 20.0 create it ("Domestic" on the generic chart) and
  attach the domestic taxes to it; a tax is `is_domestic` when it has no positions or belongs to the domestic one.
- Selection on documents: `account.move.fiscal_position_id` is computed from the partner and delivery address
  (`_compute_fiscal_position_id` → `account.fiscal.position._get_fiscal_position`): the partner's (or delivery
  address's) `property_account_position_id` first; otherwise, if the partner has a country, the first
  `auto_apply` position of the company whose criteria match, ordered by company depth then `sequence`. Line taxes
  are then `map_tax(product taxes)` (`account.move.line._get_computed_taxes`).
- Plan recipe for "0% on exports": upsert the position, then upsert the 0% tax with
  `fiscal_position_ids: {"$set": [position]}` and `original_tax_ids: {"$set": [domestic sales tax]}`, then either
  `auto_apply` criteria on the position or `property_account_position_id` on the partners (with the op's `company`).

## How to verify
- The replacement tax: `account.tax.fiscal_position_ids` contains the position and `original_tax_ids` contains the
  domestic tax.
- The position: `account.fiscal.position.tax_ids` contains the replacement tax (and the position's own `tax_map`
  shows the pair, as JSON keyed by tax id string).
- The partner: `res.partner.property_account_position_id` (read with the company in context).
- On an invoice for that partner: `account.move.fiscal_position_id` is the position, and each product line's
  `account.move.line.tax_ids` is the replacement tax, not the domestic one (scenario
  `accounting_fiscal_position_export`: live, the export invoice read `tax_ids = [the 0% tax]`, `amount_tax = 0`, the
  domestic one kept the 15% tax). Read the fields; do **not** call `map_tax` over RPC: it takes a recordset
  and fails with `'int' object has no attribute 'id'` (S2 finding A1).

## Pitfalls
- **Old recipe does not exist any more.** Tutorials and model memory describe a `tax_ids` one2many of
  `account.fiscal.position.tax` lines (`tax_src_id` / `tax_dest_id`) on the position; neither name exists in
  `odoo/addons/account/models@20.0`. In 20.0
  `account.fiscal.position.tax_ids` is a many2many to `account.tax`, and the source → destination pairs are
  `original_tax_ids` on the destination tax.
- A tax restricted to positions disappears under any other position. On the live template DB the domestic 15%
  taxes belong to the "Domestic" position; under a new export position they are **removed** (not kept) unless a
  replacement tax lists them in `original_tax_ids`. Missing mapping shows up as invoice lines with no tax at all.
- `property_account_position_id` is company dependent: set it per company (op `company`), it does not propagate.
- With several `auto_apply` positions that match (e.g. one without any country), the lowest `sequence` wins. The
  generic chart's "Foreign Trade" position (sequence 20, no country) matches every foreign partner of company 1
  on the live template DB; a new export position must sort before it or be set on the partner.
- `country_id` + `foreign_vat` on a position means "the company is registered for VAT in that country"; it is not
  a customer filter only, and it triggers foreign tax creation (`action_create_foreign_taxes`).

## Alternatives
- Separate products or a different default tax per product category, only when the tax really depends on the
  item, not on the partner.
- A tax-exempt partner can also be handled by a position with replacement 0% taxes, rather than by removing taxes
  by hand on each invoice.

## Mexico notes
The `mx` chart creates positions such as "MX Domestic", "Foreign Customer", "Freight", "Honorarium" and "Lease"
(seen on the live template DB, not `auto_apply`), whose taxes are linked with the same tax-side fields. Withholding
regimes for individuals (honorarium, lease) are fiscal positions set on the partner. See the `l10n_mx` area.
