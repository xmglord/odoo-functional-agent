---
title: Discounts on sales order lines and global discounts
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales/products_prices/prices/discounts.html, odoo/addons/sale/wizard/res_config_settings.py@20.0, odoo/addons/sale/wizard/sale_order_discount.py@20.0, odoo/addons/sale/models/sale_order_line.py@20.0, odoo/addons/sale/models/res_company.py@20.0, odoo/addons/sale/models/res_groups.py@20.0, odoo/addons/sale/views/sale_order_views.xml@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [sale]
models: [sale.order.line, sale.order.discount, sale.order, res.company, res.config.settings]
settings: [group_discount_per_so_line]
---

## When to use
- If salespeople negotiate a percentage off individual lines, enable **Discounts** (`group_discount_per_so_line`),
  because the `discount` column on order lines (and on invoices) is hidden from users without
  `sale.group_discount_per_so_line`.
- If the business gives one discount on the whole order (5% for paying upfront, a fixed amount as a goodwill
  gesture), use the order's **Discount** button (wizard `sale.order.discount`): it either writes the percentage on
  every line or adds a separate discount line.
- If the discount is structural (every order for a customer group), use a pricelist instead (see the pricelists
  entry): it applies automatically and needs no manual step.

## Configuration
- Setting: `res.config.settings.group_discount_per_so_line` ("Discounts"), implies `sale.group_discount_per_so_line`
  (`odoo/addons/sale/wizard/res_config_settings.py@20.0`; the settings model lives in `wizard/`, not `models/`, in
  20.0).
- Line field: `sale.order.line.discount` ("Discount (%)", float, computed from the pricelist but writable). It is a
  percentage: `10.0` means 10%. Negative values raise the price.
- Order button: `sale.order.action_open_discount_wizard` opens `sale.order.discount` with fields
  `sale_order_id`, `discount_type`, `discount_percentage`, `discount_amount`. Apply with `action_apply_discount`.
  - `discount_type = 'sol_discount'` ("On All Order Lines"): writes `discount = discount_percentage * 100` on every
    non-section line.
  - `'so_discount'` ("Global Discount"): adds discount lines (product `res.company.sale_discount_product_id`) for
    `discount_percentage` of the order, split per tax.
  - `'amount'` ("Fixed Amount"): adds discount lines for `discount_amount`.
  - `discount_percentage` is a fraction in the wizard: `0.1` means 10%; values above `1.0` raise "Invalid discount
    amount".
- `res.company.sale_discount_product_id`: the service product used for discount lines. If empty, the wizard creates
  one the first time, when the user may create products and write the company.

## How to verify
- Setting: `base.group_user` has `sale.group_discount_per_so_line` in `implied_ids`.
- Per-line: `sale.order.line.discount` holds the percentage and `price_subtotal` equals
  `price_unit * product_uom_qty * (1 - discount / 100)` before taxes.
- Global discount: the order has an extra `sale.order.line` whose `product_id` is the company's
  `sale_discount_product_id`, with a negative `price_unit`; `amount_untaxed` dropped by the expected amount.
- `res.company.sale_discount_product_id` is set after the first global discount.

## Pitfalls
- Two scales: the line field is 0-100, the wizard's `discount_percentage` is 0-1. Writing `0.1` to a line gives a
  0.1% discount.
- `discount` is a computed, stored, writable field: with pricelists and Discounts both enabled, a pricelist rule
  that is a plain discount fills it, and recomputation (changing product or quantity in the UI) can overwrite a
  manual value.
- In 20.0, `sale.group_discount_per_so_line` is a "light" group (`_get_light_group_xmlids` in
  `odoo/addons/sale/models/res_groups.py@20.0`); feature checks in code use
  `res.groups._is_feature_enabled('sale.group_discount_per_so_line')`, which tests whether the superuser has the
  group. Enabling it through settings is still the supported path.
- The global-discount product must be a service with invoice policy "ordered quantities" (its domain), or the
  discount is not invoiced together with the goods.

## Alternatives
- Pricelists for automatic, rule-based prices.
- Loyalty and coupon programs (`module_sale_loyalty`) for conditional promotions and codes.
- A negative-price line with a dedicated service product, when the business wants the discount visible as its own
  line without the wizard.
