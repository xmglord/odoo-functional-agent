---
title: Bill control (ordered vs received quantities) and vendor bills from purchase orders
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/purchase/models/product.py@20.0, odoo/addons/purchase/models/purchase_order.py@20.0, odoo/addons/purchase/models/purchase_order_line.py@20.0, odoo/addons/purchase_stock/models/purchase_order_line.py@20.0, odoo/addons/purchase/models/res_config_settings.py@20.0, odoo/addons/account/models/account_move.py@20.0, enterprise/account_3way_match/models/account_invoice.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [purchase, purchase_stock, account]
models: [product.template, purchase.order, purchase.order.line, account.move, account.move.line]
settings: [module_account_3way_match]
---

## When to use
- If the business pays only for goods that actually arrived (most stocked goods), use **received quantities**
  (`purchase_method = 'receive'`), because the bill then follows `qty_received` and a bill for goods still in
  transit has nothing to bill.
- If the vendor bills upfront or the item is a service or subscription, use **ordered quantities**
  (`purchase_method = 'purchase'`), because the full ordered quantity is billable as soon as the order is
  confirmed.
- If accounts payable must hold bills until order, receipt and bill agree, add 3-way matching
  (`module_account_3way_match`, Enterprise module "Vendor Bill: Release to Pay").

## Configuration
- Product: `product.template.purchase_method` ("Control Policy", selection `purchase` "On ordered quantities" /
  `receive` "On received quantities"; computed, stored, writable, `precompute`). Services always compute to
  `purchase`; goods take the `ir.default` for `product.template.purchase_method`, falling back to `receive`.
- There is **no settings field** for the default in 20.0 (no `default_purchase_method` in
  `res.config.settings`; checked live). Set the policy per product, in the same write as `type`.
- Order line (`purchase.order.line`):
  - `qty_received` is filled from done stock moves when `qty_received_method = 'stock_moves'` (every goods line once
    `purchase_stock` is installed), else entered by hand (`manual`, through `qty_received_manual`).
  - `qty_to_invoice` = `product_qty - qty_invoiced` for `purchase`, `qty_received - qty_invoiced` for `receive`, and
    0 while the order is not in state `purchase`.
  - `qty_invoiced` sums the posted and draft bill lines linked through `account.move.line.purchase_line_id`.
- Order: `purchase.order.invoice_status` (`no` "Nothing to Bill", `to invoice` "Waiting Bills", `invoiced` "Fully
  Billed") follows the lines' `qty_to_invoice`; `receipt_status` (`pending`, `partial`, `full`) follows
  `qty_received`.
- Creating the bill: `purchase.order.action_create_invoice` creates one `account.move` with
  `move_type = 'in_invoice'` per vendor/currency, with one line per order line for its `qty_to_invoice`, and
  returns a window action on the bill (not a wizard). Post it with `account.move.action_post` after setting
  `invoice_date`.

## How to verify
- Product: `product.template.purchase_method` on each product the requirement names.
- After `button_confirm`, policy `receive`, nothing received: line `qty_to_invoice == 0`, order
  `invoice_status == 'no'`, `receipt_status == 'pending'`.
- After the receipt is validated: line `qty_received` equals the received quantity, `qty_to_invoice` equals it too,
  order `invoice_status == 'to invoice'`.
- After the bill is created and posted: `account.move` with `move_type == 'in_invoice'`, `state == 'posted'`,
  found through `invoice_line_ids.purchase_line_id.order_id`; line `qty_invoiced` equals the billed quantity; order
  `invoice_status == 'invoiced'` and `invoice_count >= 1`. Observed on a 20.0 demo DB (scenario
  `purchase_po_to_bill`).

## Pitfalls
- **A vendor bill needs a bill date to post.** `action_post` on an `in_invoice` without `invoice_date` raises
  "The Bill/Refund date is required to validate this document." Customer invoices default the date; bills do not.
- **No "nothing to bill" error.** Unlike the sales invoice wizard, `action_create_invoice` does not refuse when
  nothing is billable: with a `receive` product and no receipt it still creates a draft bill whose line quantity
  is 0. Check `invoice_status == 'to invoice'` first.
- **Two- and three-step receipts count at the first step.** `qty_received` rises when the receipt into
  `WH/Input` is done, before the storage transfer reaches `WH/Stock` (observed live with two-step receipts).
  Received means "arrived at the dock", not "on the shelf".
- The default for new goods is an `ir.default`, so changing it affects only products created afterwards; changing
  a product's `type` recomputes `purchase_method`.
- The order line fields are `uom_id` and `tax_ids` in 20.0 (not `product_uom` / `taxes_id`).

## Alternatives
- Manual received quantities (`qty_received_method = 'manual'`, the order's `action_receive`) for services or when
  stock is not managed in Odoo.
- Down payments on the purchase order (lines with `is_downpayment`) when the vendor asks for an advance.
- 3-way matching (Enterprise): bills get `release_to_pay` (`yes` / `no` / `exception`) from order, receipt and bill
  quantities, so payment runs can filter on it.
