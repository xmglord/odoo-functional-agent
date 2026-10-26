---
title: Multi-step receipts and deliveries (warehouse steps)
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/stock/models/res_config_settings.py@20.0, odoo/addons/stock/models/stock_warehouse.py@20.0, odoo/addons/stock/models/stock_picking_type.py@20.0, odoo/addons/stock/models/stock_move.py@20.0, odoo/addons/purchase_stock/models/purchase_order_line.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [stock, purchase_stock]
models: [stock.warehouse, stock.picking.type, stock.picking, stock.move, stock.route, res.config.settings]
settings: [group_stock_multi_locations, group_stock_adv_location]
---

## When to use
- If goods are unloaded at a dock and put away later (counting, labelling, cross-checking before they become
  available), use **two-step receipts** (`reception_steps = 'two_steps'`), because stock sits in `WH/Input` until a
  separate storage transfer moves it to `WH/Stock`.
- If incoming goods must pass a quality check before storage, use **three steps** (`three_steps`): Input, Quality
  Control, then Stock.
- If orders are picked in the warehouse and handed to a carrier at a shipping area, use **pick then deliver**
  (`delivery_steps = 'pick_ship'`); add packing with `pick_pack_ship`.
- If goods go straight from the truck to the shelf and from the shelf to the customer, keep the defaults
  (`one_step`, `ship_only`): every extra step is one more transfer for someone to validate.

## Configuration
- Settings (`res.config.settings`, `odoo/addons/stock/models/res_config_settings.py@20.0`):
  - `group_stock_multi_locations` ("Storage Locations", implies `stock.group_stock_multi_locations`).
  - `group_stock_adv_location` ("Multi-Step Routes", implies `stock.group_adv_location`). The settings screen turns
    on Storage Locations with it through an onchange; a plan does not run onchanges, so set **both** to `true`.
- Warehouse (`stock.warehouse`, demo main warehouse xmlid `stock.warehouse0`):
  - `reception_steps`: `one_step` "Receive and Store (1 step)", `two_steps` "Receive then Store (2 steps)",
    `three_steps` "Receive, Quality Control, then Store (3 steps)".
  - `delivery_steps`: `ship_only` "Deliver (1 step)", `pick_ship` "Pick then Deliver (2 steps)", `pick_pack_ship`
    "Pick, Pack, then Deliver (3 steps)".
  - Writing either field activates or archives the locations (`wh_input_stock_loc_id`, `wh_qc_stock_loc_id`,
    `wh_output_stock_loc_id`, `wh_pack_stock_loc_id`) and operation types (`in_type_id`, `qc_type_id`,
    `store_type_id`, `pick_type_id`, `pack_type_id`, `out_type_id`), and rewrites the receipt and delivery routes.
- How the steps chain (`get_rules_dict`): the first step is a pull rule (Vendors to stock through `in_type_id`,
  whose default destination becomes `WH/Input`); each later step is a **push** rule. The storage transfer
  (`store_type_id`, `WH/Input` to `WH/Stock`) is created when the receipt is validated, not when the purchase order
  is confirmed. Deliveries mirror this: the pick is created at confirmation, the delivery when the pick is done.

## How to verify
- Settings: `base.group_user` has `stock.group_adv_location` and `stock.group_stock_multi_locations` in
  `implied_ids`.
- Warehouse: `stock.warehouse.reception_steps == 'two_steps'` (or the requested value);
  `store_type_id.active == True`; `in_type_id.default_location_dest_id == wh_input_stock_loc_id`.
- Flow (observed on a 20.0 demo DB, scenario `inventory_two_step_receipt`): after `button_confirm` on a purchase
  order there is one receipt (`picking_type_id` = the warehouse's `in_type_id`, destination `WH/Input`); after it is
  validated a picking with `picking_type_id` = `store_type_id` exists, found through
  `move_ids.move_orig_ids.picking_id`; after that one is validated, a `stock.quant` in `stock.stock_location_stock`
  holds the quantity.

## Pitfalls
- **The storage transfer is not linked to the purchase order.** Its moves have no `purchase_line_id`, so
  `stock.picking.purchase_id` is empty and it is not in `purchase.order.picking_ids`. Find it through
  `move_ids.move_orig_ids` from the receipt.
- **`qty_available` already counts goods in `WH/Input`.** Input is an internal location of the warehouse, so the
  product's on-hand quantity rises at the first step. To prove the put-away, read `stock.quant` in
  `WH/Stock`.
- **Bills follow the first step.** `purchase.order.line.qty_received` rises when the receipt into Input is done
  (see the bill control entry).
- Turning `group_stock_multi_locations` off while a company has several warehouses raises "You can't deactivate the
  multi-location feature if you have more than one warehouse per company".
- On the 20.0 demo template, Multi-Step Routes is **off** and the main warehouse is `one_step`, so applying these
  values is a real change (not a pre-state).

## Alternatives
- Putaway rules on `WH/Stock` sublocations (Storage Locations alone) when the goal is "where to store" rather than
  "store later".
- Reception reports and batch transfers (`group_stock_picking_batch`) to organize put-away work without an extra
  step.
- A quality module (`module_quality_control`) with checks on the receipt itself instead of a third step.
