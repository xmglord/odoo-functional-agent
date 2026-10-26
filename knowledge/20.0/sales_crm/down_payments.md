---
title: Down payments on sales orders
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales/invoicing/down_payment.html, odoo/addons/sale/wizard/sale_make_invoice_advance.py@20.0, odoo/addons/sale/models/res_company.py@20.0, odoo/addons/sale/wizard/res_config_settings.py@20.0, odoo/addons/sale/models/sale_order_line.py@20.0, odoo/addons/account/models/account_tax.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [sale]
models: [sale.advance.payment.inv, sale.order, sale.order.line, res.company, account.move]
settings: [downpayment_account_id]
---

## When to use
- If the business asks for part of the price before it starts work or orders material (custom furniture, projects,
  large B2B orders), invoice a **down payment** from the confirmed order, because the advance is then tracked on
  the order and deducted automatically from the final invoice.
- If the advance must be paid before the order is even confirmed, use online payment with a prepayment percentage
  instead (see the online signature and payment entry).
- If down payments must be booked on a specific account (customer advances as a liability rather than income), set
  the company's down payment account.

## Configuration
- Wizard `sale.advance.payment.inv` (the order's "Create Invoice" button), fields:
  - `sale_order_ids` (a down payment needs exactly one order)
  - `advance_payment_method`: `delivered` ("Regular invoice"), `percentage` ("Down payment (percentage)"),
    `fixed` ("Down payment (fixed amount)")
  - `amount`: percentage on a 0-100 scale for `percentage`
  - `fixed_amount`: amount in the order currency for `fixed`
  - `deduct_down_payments` (default true): on a regular invoice, deduct the posted down payments
  - `consolidated_billing` (default true): one invoice per customer/address across orders
  - method `create_invoices`
- A down payment creates, on the order, a "Down Payments" section line and `sale.order.line` records with
  `is_downpayment = True` (split by tax when the order has several taxes), and a draft customer invoice (`account.move`, `move_type =
  'out_invoice'`) with those lines.
- Account: `res.company.downpayment_account_id` (settings related field `downpayment_account_id`; domain:
  accounts of type `income`, `income_other` or `liability_current`). Without it, the product's down payment or
  income account is used.
- No down payment product is configured in 20.0: the lines are product-less down payment lines.

## How to verify
- After the down payment: the order has `sale.order.line` records with `is_downpayment == True`; the invoice
  (`invoice_ids` on the order) has an amount equal to the percentage of `amount_total` (or the fixed amount);
  its `state` is `draft` until posted.
- After posting it and creating the regular invoice with `deduct_down_payments` true: the final invoice contains a
  negative line for the down payment (read its `invoice_line_ids`: `price_subtotal` < 0 on the down payment line).
- Account: `res.company.downpayment_account_id` holds the chosen account.

## Pitfalls
- Two scales across wizards: the down payment `amount` is 0-100 (`10` = 10%), while the global-discount wizard's
  `discount_percentage` is 0-1.
- Only posted down payments are deducted (`amount_invoiced` counts "only confirmed down payments"); deducting from a
  draft down payment invoice does not work.
- Older versions configured a down payment product (`sale.default_deposit_product_id` /
  `deposit_default_product_id`); it does not exist in 20.0. Do not plan it.
- A down payment on a delivered-policy order is allowed before delivery, but the regular invoice still waits for the
  delivery.
- The wizard needs one order for a down payment; with several `sale_order_ids` only the regular invoice works.

## Alternatives
- Online prepayment (`prepayment_percent` with `portal_confirmation_pay`) when the customer should pay before
  confirmation.
- Payment terms with an immediate first installment (see the payment terms entry) when the invoice is created for
  the full amount upfront.

## Mexico notes
In Mexico a down payment received is usually documented as its own CFDI and related to the final invoice; how
`l10n_mx_edi` handles that is covered in the `l10n_mx` area.
