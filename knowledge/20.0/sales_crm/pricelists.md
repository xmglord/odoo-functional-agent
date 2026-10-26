---
title: Pricelists and customer-specific prices
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales/products_prices/prices/pricing.html, odoo/addons/product/models/res_config_settings.py@20.0, odoo/addons/product/models/product_pricelist.py@20.0, odoo/addons/product/models/product_pricelist_item.py@20.0, odoo/addons/product/models/res_partner.py@20.0, odoo/addons/sale/models/sale_order.py@20.0, odoo/addons/sale/models/product_pricelist_item.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [product, sale]
models: [product.pricelist, product.pricelist.item, res.partner, sale.order, res.config.settings]
settings: [group_product_pricelist]
---

## When to use
- If some customers pay different prices than the list price (wholesale vs retail, a key account, a country in
  another currency), enable **Pricelists** (`group_product_pricelist`) and assign a `product.pricelist` to those
  customers, because the order then prices every line from the customer's pricelist automatically.
- If prices depend on quantity (volume breaks) or on a date range (seasonal promotion), use pricelist rules with
  `min_quantity` or `date_start`/`date_end`.
- If the business sells in more than one currency, create one pricelist per currency: the order currency
  (`sale.order.currency_id`) comes from the pricelist.
- If the only need is an occasional manual discount on a line, use line discounts instead (see the discounts entry).

## Configuration
- Setting: `res.config.settings.group_product_pricelist` ("Pricelists"), implies `product.group_product_pricelist`
  (`odoo/addons/product/models/res_config_settings.py@20.0`). Set it explicitly: the sale settings method that
  is meant to switch it on with line discounts (`_onchange_group_discount_per_so_line`) is decorated
  `@api.depends`, not `@api.onchange`, in 20.0 source, so it is not guaranteed to run (not checked live).
- `product.pricelist`: `name`, `active`, `sequence`, `currency_id`, `company_id`, `country_group_ids`, `item_ids`.
- `product.pricelist.item` (a rule):
  - scope: `applied_on` (`3_global`, `2_product_category`, `1_product`, `0_product_variant`; computed from which of
    `categ_id`, `product_tmpl_id`, `product_id` is set), `min_quantity`, `date_start`, `date_end`, `uom_id`.
  - price type: `compute_price` in **`discount`**, **`markup`** (label "Surcharge") or **`fixed`** (default).
  - values: `fixed_price`; `price_discount` (percent off, used by `discount`); `price_markup` (percent added, the
    negative of `price_discount`); `price_round`, `price_surcharge` (label "Extra Fee"), `price_min_margin`,
    `price_max_margin`.
  - base: `base` in `list_price` (Sales Price), `standard_price` (Cost), `pricelist` (with `base_pricelist_id`).
- Customer assignment: `res.partner.property_product_pricelist` (computed, writable, per company). The stored
  value is the company-dependent `specific_property_product_pricelist`. Without one, the partner gets the first
  pricelist matching their country group, then the first pricelist without a country group.
- On the order, `sale.order.pricelist_id` is computed from `partner_id.property_product_pricelist` while the order
  is a draft; `currency_id` follows the pricelist.

## How to verify
- Setting: `base.group_user` has `product.group_product_pricelist` in `implied_ids`.
- Pricelist and rules: read `product.pricelist` (`currency_id`, `item_ids`) and each `product.pricelist.item`
  (`applied_on`, `compute_price`, `price_discount` or `fixed_price`, `min_quantity`, `product_tmpl_id` or `categ_id`).
- Assignment: `res.partner.property_product_pricelist` on the customer equals the pricelist (read with the right
  company in context in multi-company databases).
- Effect: a new `sale.order` for that customer has `pricelist_id` = the pricelist, and its line's `price_unit`
  matches the rule (for example list price × (1 − `price_discount`/100)).

## Pitfalls
- **Price types changed.** Older versions used `compute_price` values `fixed`, `percentage` (with `percent_price`)
  and `formula`. In 20.0 the selection is `discount`, `markup`, `fixed`, and `percent_price` does not exist. The
  20.0 docs page still describes "Discount / Formula / Fixed Price"; the source wins. A "formula" style rule is a
  `discount` or `markup` rule with `price_round`, `price_surcharge` or margins filled in.
- The default for `compute_price` is `fixed`; a rule created with only `price_discount` and no `compute_price` sets
  a fixed price of 0.
- `pricelist_id` is recomputed only on draft orders; changing the customer's pricelist does not reprice confirmed
  orders. In the UI, changing an order's pricelist reprices its lines through the onchange
  `_onchange_pricelist_id_recompute_prices`; a JSON-2 `write` of `pricelist_id` runs no onchange, so existing line
  prices stay as they were.
- Pricelists with `company_id` set are invisible to other companies.
- Whether the customer sees the discount as a separate column depends on line discounts being enabled and on the
  rule being a plain discount (`is_plain_discount`) (`odoo/addons/sale/models/product_pricelist_item.py@20.0`).

## Alternatives
- For a few fixed customer prices, a `fixed` rule per product on a dedicated pricelist is clearer than
  percentages.
- For promotions with conditions (coupons, buy X get Y), `module_loyalty` / `module_sale_loyalty` instead of
  pricelists.
- For one-off negotiations, a manual line discount or the global discount wizard.
