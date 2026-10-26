---
title: Invoicing policy (ordered vs delivered quantities)
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales/invoicing/invoicing_policy.html, odoo/addons/sale/models/res_company.py@20.0, odoo/addons/sale/wizard/res_config_settings.py@20.0, odoo/addons/sale/models/product_template.py@20.0, odoo/addons/sale/models/sale_order_line.py@20.0, odoo/addons/sale/models/sale_order.py@20.0, odoo/addons/sale/wizard/sale_make_invoice_advance.py@20.0, odoo/addons/sale_stock/models/sale_order_line.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [sale, sale_stock]
models: [res.company, product.template, sale.order, sale.order.line, sale.advance.payment.inv, res.config.settings]
settings: [sale_invoice_policy, sale_automatic_invoice]
---

## When to use
- If the business bills when the order is agreed (subscriptions, prepaid goods, fixed-price services, eCommerce
  paid upfront), use **ordered quantities** (`invoice_policy = 'order'`), because the full order is invoiceable as
  soon as it is confirmed.
- If the business bills only what actually left the warehouse (partial shipments, backorders, B2B goods on credit),
  use **delivered quantities** (`invoice_policy = 'delivery'`), because the invoice then follows `qty_delivered`
  and never bills goods that were not shipped.
- If both kinds of products are sold, set the company default to the common case and override it per product: the
  policy is a product field.
- If invoices must be created and paid automatically when an online payment is confirmed, enable
  `sale_automatic_invoice`; it requires the ordered-quantities default.

## Configuration
- Company default: `res.company.sale_invoice_policy` (selection `order` / `delivery`, default `order`), exposed in
  settings as the related field `res.config.settings.sale_invoice_policy` ("Invoicing Policy").
- Product: `product.template.invoice_policy` (same selection, stored, computed with `precompute`): a new product
  takes the company's `sale_invoice_policy`; it can be written per product.
- Order line: `sale.order.line.invoice_policy` (computed, not stored) is the product's policy, or the company's for
  lines without a product. `qty_to_invoice` = `product_uom_qty - qty_invoiced` for `order`, and
  `qty_delivered - qty_invoiced` for `delivery`.
- Delivered quantity: `sale.order.line.qty_delivered`, filled from validated pickings when `sale_stock` is installed
  (`qty_delivered_method = 'stock_move'`), or entered manually (`manual`) for services.
- Automatic invoicing: `res.company.sale_automatic_invoice` (settings field `sale_automatic_invoice`); the settings
  onchange clears it when the policy is not `order`. It toggles the cron `sale.send_invoice_cron`.
- Creating the invoice: wizard `sale.advance.payment.inv` with `sale_order_ids`, `advance_payment_method =
  'delivered'` ("Regular invoice"), then `create_invoices`. It calls `sale.order._create_invoices`, which raises a
  `UserError` ("Cannot create an invoice. No items are available to invoice.") when no line has `qty_to_invoice`.

## How to verify
- Company default: `res.company.sale_invoice_policy` on the company.
- Product: `product.template.invoice_policy` on each product the business mentioned.
- After confirmation (ordered policy): `sale.order.invoice_status == 'to invoice'` and each line's
  `qty_to_invoice == product_uom_qty`.
- After confirmation (delivered policy), before delivery: `invoice_status == 'no'`, `qty_to_invoice == 0`; after the
  picking is validated: `qty_delivered` equals the shipped quantity and `invoice_status == 'to invoice'`.
- After invoicing: `qty_invoiced` equals the invoiced quantity, `invoice_status == 'invoiced'`, and `invoice_ids`
  lists the `account.move`.

## Pitfalls
- **Moved from a `default_` setting to the company.** Older versions set the default through a settings field
  `default_invoice_policy` (an `ir.default` on `product.template`). In 20.0 it is the company field
  `sale_invoice_policy`; `default_invoice_policy` does not exist.
- Changing the company default affects only products created afterwards; existing products keep their value.
- In the 20.0 source, `_compute_invoice_policy` on `product.template` resets the policy to `order` when an existing
  product's `type` is changed to goods (`consu`). Set `invoice_policy` after changing the type, or in the same
  write.
- Ordered-policy services delivered beyond the ordered quantity create an overage (`qty_overage`); they are only
  invoiced when the order's `invoice_overages` is set.
- A delivered-policy order cannot be invoiced before delivery; the invoice wizard returns a `UserError`, not an
  empty invoice.
- `qty_delivered` for storable goods comes from stock moves; writing it by hand on such a line is overwritten.

## Alternatives
- Down payments (see the down payments entry) to bill part of a delivered-policy order upfront.
- Online payment with prepayment on the quotation, so the customer pays before confirmation while the invoice still
  follows deliveries.
- Manual "close for invoicing" (`sale.order.action_close_invoicing`, field `invoicing_closed`) when the remainder
  will never be invoiced.

## Mexico notes
Invoices created from sales orders in a Mexican company are CFDI documents once posted; the invoicing policy only
decides when they are created. See the `l10n_mx` area for CFDI requirements.
