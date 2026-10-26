---
title: Backorders on partial receipts and deliveries
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/stock/models/stock_picking_type.py@20.0, odoo/addons/stock/models/stock_picking.py@20.0, odoo/addons/stock/wizard/stock_backorder_confirmation.py@20.0, odoo/addons/stock/models/stock_move.py@20.0, odoo/addons/stock/models/res_config_settings.py@20.0, odoo/addons/stock/models/res_company.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [stock, purchase_stock]
models: [stock.picking.type, stock.picking, stock.move, stock.backorder.confirmation, stock.backorder.confirmation.line, res.company, res.config.settings]
settings: [picking_policy]
---

## When to use
- If a vendor delivers part of an order and the rest is still expected, keep **Create Backorder = Ask** (`ask`, the
  default) or set **Always** (`always`), because validating the partial receipt then leaves a new transfer (the
  backorder) for the missing quantity.
- If anything not received now will never come (the vendor cancels the rest, or the business re-orders instead),
  set **Never** (`never`), because the remaining quantity is cancelled on validation.
- If warehouse staff must decide case by case, keep **Ask**: validation opens the "Create Backorder?" wizard.
- If customers should receive one complete shipment instead of partial ones, set the shipping policy
  `picking_policy = 'one'` ("When all products are ready"); `direct` ("As soon as possible, with back orders")
  ships what is available.

## Configuration
- Per operation type: `stock.picking.type.create_backorder` (selection `ask` / `always` / `never`, required,
  default `ask`). Each warehouse has its own receipt type (`stock.warehouse.in_type_id`; demo xmlid
  `stock.picking_type_in`) and delivery type (`out_type_id`).
- Company shipping policy: `res.company.picking_policy` (setting `picking_policy`, `direct` / `one`); saving the
  setting also writes `move_type` on the company's operation types.
- Quantities on a transfer: each `stock.move` has the demand `product_uom_qty` and the done quantity `quantity`,
  plus `picked`; the unit field is `uom_id` (not `product_uom`).
- Validation, `stock.picking.button_validate`:
  1. If some moves have a quantity but none is `picked`, all moves are marked `picked`
     (`_pre_action_done_hook`).
  2. With `create_backorder = 'ask'` and a picked quantity below the demand (`_check_backorder`), it returns a
     window action on `stock.backorder.confirmation` with **no `res_id`**; the context carries
     `default_pick_ids`, `default_show_transfers` and `button_validate_picking_ids`.
  3. With `always` the backorder is created without asking; with `never` the rest is cancelled.
- Wizard `stock.backorder.confirmation` (`pick_ids`, `show_transfers`, `backorder_confirmation_line_ids` with
  `picking_id` / `to_backorder`, filled by `default_get`):
  - `process` ("Create Backorder"): validates again with `skip_backorder`, creating the backorder for the lines
    marked `to_backorder` (all, by default).
  - `process_cancel_backorder` ("No Backorder"): validates with `picking_ids_not_to_backorder`, so the remaining
    quantity is cancelled (unless the operation type is `always`), and logs the shortfall.
- `ofa` follows this wizard by itself: `stock.backorder.confirmation` maps to `process` by default; pass
  `wizards: {"stock.backorder.confirmation": "process_cancel_backorder"}` on the step for the other choice. Because
  the action has no `res_id`, `ofa` creates the wizard with the action's context first (`src/ofa/wizards.py`).

## How to verify
- Configuration: `stock.picking.type.create_backorder` on the receipt and delivery types of the warehouse.
- After validating 6 of 10 with `process` (observed on a 20.0 demo DB, scenario
  `inventory_partial_receipt_backorder`): the receipt reads `state == 'done'` and its move `product_uom_qty == 6`
  (the demand shrinks to the done quantity); exactly one `stock.picking` has `backorder_id` = the receipt, with a
  move of `product_uom_qty == 4`; the purchase line reads `qty_received == 6` and the order
  `receipt_status == 'partial'`.
- With `process_cancel_backorder` (from source, not run live): no picking has `backorder_id` = the receipt, the
  remaining move is `cancel`, and the purchase line keeps `qty_received` at the received quantity.

## Pitfalls
- **The wizard has no record.** Code that only follows wizard actions with a `res_id` (as for `confirm.stock.sms`)
  stops here; the wizard must be created from the action's `context`.
- Validating with no quantity at all raises "You can't validate an empty transfer" (no moves) or the "Transfer
  trouble alert!" zero-quantity error; it does not ask for a backorder.
- A backorder of a receipt keeps its `purchase_line_id`, so `purchase.order.picking_ids` lists both the done
  receipt and the backorder.
- Returns ignore `create_backorder` (`_should_ignore_backorders` is true when the picking has a `return_id`).
- Lowering `product_uom_qty` on a move (instead of `quantity`) does not create a backorder; the help of the field
  says so.

## Alternatives
- `create_backorder = 'never'` plus a new purchase order when the vendor will not ship the rest.
- "Split" on a transfer (`stock.picking.action_split_transfer`) to separate part of a transfer before validation.
