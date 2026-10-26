---
title: Taxes and tax groups
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/account_tax.py@20.0, odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/res_config_settings.py@20.0, odoo/addons/account/models/product.py@20.0, odoo/addons/account/models/account_move_line.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account]
models: [account.tax, account.tax.group, account.tax.repartition.line, res.company, product.template, product.product, account.move.line, res.config.settings]
settings: [sale_tax_id, purchase_tax_id, account_price_include, tax_calculation_rounding_method, tax_exigibility]
---

## When to use
- If the business charges or pays VAT/sales tax, the taxes come with the country's chart template; configure
  **which tax is the default** (`sale_tax_id`, `purchase_tax_id`) and **which products carry which tax**
  (`taxes_id`, `supplier_taxes_id`) instead of creating taxes.
- Create a new `account.tax` only for a rate the template does not have (a special rate, a withholding, a 0%
  export tax for a fiscal position).
- If shop prices are shown tax-included (B2C retail), set the company default `account_price_include =
  'tax_included'`; for B2B price lists that exclude tax keep `tax_excluded`. A single tax can override it with
  `price_include_override`.
- If tax is due when the customer pays, not when the invoice is issued (cash-basis regimes), enable
  `tax_exigibility` and set `tax_exigibility = 'on_payment'` on those taxes.
- Tax groups (`account.tax.group`) decide how taxes are **summed and labelled in invoice totals** (e.g. one "VAT
  16%" line); use them to group several taxes into one subtotal, not to compute anything.

## Configuration
- `account.tax`: `name`, `type_tax_use` (`sale`, `purchase`, `none`; `none` only inside a group of taxes),
  `amount_type` (`percent`, `fixed`, `division` = percentage tax included, `group` = group of taxes with
  `children_tax_ids`), `amount`, `tax_scope` (`service`, `consu`), `price_include_override` (`tax_included`,
  `tax_excluded`, empty = company default), `include_base_amount`, `is_base_affected`, `tax_group_id`,
  `invoice_label`, `country_id`, `tax_exigibility` (`on_invoice`, `on_payment`), `company_id` (required, read-only
  after creation, defaults to the current company), `active`.
- Repartition: `invoice_repartition_line_ids` / `refund_repartition_line_ids` (`account.tax.repartition.line`:
  `repartition_type` `base`/`tax`, `factor_percent`, `account_id`, `tag_ids` = tax report grids). When none are
  given, the tax gets one base and one tax line per document type (`_compute_invoice_repartition_line_ids`), with
  no account on the tax line.
- Fiscal-position fields (20.0): `fiscal_position_ids`, `original_tax_ids` ("Replaces"), `replacing_tax_ids`
  (read-only inverse), computed `is_domestic`. See the fiscal positions entry.
- `account.tax.group`: `name`, `sequence`, `company_id`, `country_id` (computed from the company's fiscal country),
  `preceding_subtotal` (label of a subtotal shown before this group). A tax without an explicit group gets the first
  group of its company and country (`_compute_tax_group_id`).
- Company defaults (settings fields are related to the company): `sale_tax_id` → `res.company.account_sale_tax_id`,
  `purchase_tax_id` → `account_purchase_tax_id`, `account_price_include`, `tax_calculation_rounding_method`
  (`round_per_line`, `round_globally`), `tax_exigibility` (cash basis switch).
- Products: `taxes_id` (sales) and `supplier_taxes_id` (purchases); new products default to the companies'
  `account_sale_tax_id` / `account_purchase_tax_id`.
- Invoice lines: `account.move.line.tax_ids`, computed from the product's taxes filtered to the invoice company,
  falling back to the account's default `tax_ids`, then mapped by the invoice's fiscal position
  (`_get_computed_taxes`).

## How to verify
- Defaults: `res.company.account_sale_tax_id` / `account_purchase_tax_id` equal the intended taxes (live template
  DB, company 1: `account.1_sale_tax_template`, the 15% sales tax).
- A new tax: read `amount`, `amount_type`, `type_tax_use`, `price_include_override`, `tax_group_id`, `company_id`.
- Product: `product.product.taxes_id` / `supplier_taxes_id` contain the expected taxes.
- On a draft invoice: each product line's `tax_ids`, and `account.move.amount_tax` / `amount_total`.

## Pitfalls
- **Names are unique per root company, type, scope and country** (`_constrains_name`: "Tax names must be
  unique!"). A sales and a purchase tax can both be called "15%" (they are on the live template DB), two sales
  taxes cannot. Use the name plus `company_id` and `type_tax_use` as the `match` of an upsert.
- `company_id` is read-only on the form and defaults to the current company: create company taxes with the op's
  `company` set, otherwise the tax lands in the bot's default company.
- A tax that was used cannot be deleted ("You cannot delete taxes that are currently in use. Consider archiving
  them instead."); set `active = false`.
- `price_include` is a computed, non-stored field derived from `price_include_override` and the company default;
  write `price_include_override`, not `price_include`.
- Products created while several companies are allowed get the default taxes of every allowed company; the invoice
  line filters them by the invoice company, so this is harmless on invoices but confusing on the product form.
- A tax that has `fiscal_position_ids` is only kept on documents of those fiscal positions; see the fiscal positions
  entry before restricting a tax.
- Cash-basis taxes (`tax_exigibility = 'on_payment'`) book through the tax's `cash_basis_transition_account_id` and
  the company's `tax_cash_basis_journal_id`; set both with the tax. What happens when they are missing was not
  checked for this entry.

## Alternatives
- Fiscal positions to swap taxes per customer or country instead of separate products.
- Default taxes on the income/expense account (`account.account.tax_ids`) for lines without a product.
- External tax engines (AvaTax, `account_avatax`, Enterprise) for US sales tax by address.

## Mexico notes
The `mx` chart brings IVA 16%, 8% (border region), 0% and exempt, plus IEPS and withholdings, grouped in tax groups
such as `account.<company_id>_tax_group_iva_16` (seen on the live template DB). Choose among them rather than
creating rates. See the `l10n_mx` area for which tax each CFDI needs.
