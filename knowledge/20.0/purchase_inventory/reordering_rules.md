---
title: Reordering rules (min/max replenishment) and the stock scheduler
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/stock/models/stock_orderpoint.py@20.0, odoo/addons/stock/models/stock_rule.py@20.0, odoo/addons/stock/models/stock_move.py@20.0, odoo/addons/stock/models/stock_picking.py@20.0, odoo/addons/stock/data/stock_sequence_data.xml@20.0, odoo/addons/purchase_stock/models/purchase_order_line.py@20.0, odoo/addons/purchase_stock/models/stock.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [stock, purchase_stock]
models: [stock.warehouse.orderpoint, stock.rule, product.supplierinfo, purchase.order.line, ir.cron]
settings: []
---

## When to use
- If a product must never run out and is bought for stock (consumables, spare parts, fast movers), create a
  **reordering rule** with a minimum and a maximum, because Odoo then proposes or creates a purchase whenever the
  forecast drops below the minimum, for the quantity that brings it back to the maximum.
- If buyers want to review every proposal before an RFQ exists, use `trigger = 'manual'`: the need is shown in
  the replenishment report and a person orders it.
- If replenishment should run on its own, use `trigger = 'auto'` (the default), knowing it depends on the scheduler
  (see Pitfalls).
- If the product is bought only against customer orders, use MTO instead (see the routes entry).

## Configuration
- Model `stock.warehouse.orderpoint` ("Minimum Inventory Rule"):
  - `product_id` (storable product, domain `is_storable = True`), `warehouse_id`, `location_id` (both computed with
    `precompute`; default the company's warehouse stock location), `company_id`.
  - `product_min_qty`, `product_max_qty` (floats; `product_max_qty` is computed but writable).
  - `trigger`: `auto` / `manual`, default `auto`.
  - `route_id` (optional; domain: product-selectable routes or routes with a `buy`/`manufacture` rule) and
    `replenishment_uom_id` ("Multiple", rounds the quantity up to a multiple of that unit).
  - Read-only results: `qty_on_hand`, `qty_forecast`, `qty_to_order` (computed with an inverse; manual overrides go
    to `qty_to_order_manual`).
- Quantity: when `qty_forecast < product_min_qty`, `qty_to_order = max(min, max) - forecast` (forecast including
  quantities already on RFQs), rounded to the multiple.
- Vendor: the purchase uses the product's vendor lines `product.supplierinfo` (`partner_id`, `price`, `min_qty`,
  `delay`) and the warehouse's Buy rule (`buy_to_resupply`). No route on the product is needed for buying.
- Ordering now: `stock.warehouse.orderpoint.action_replenish` (the "Order Once" button) runs the rule for its
  `qty_to_order` and creates or extends a draft RFQ; `action_replenish_auto` sets `trigger = 'auto'` first.
- Scheduler: cron `stock.ir_cron_scheduler_action` ("Procurement: run scheduler", daily) runs
  `stock.rule.run_scheduler`, which recomputes and confirms every orderpoint, then retries reservations.

## How to verify
- Rule: `stock.warehouse.orderpoint` for the product with the agreed `product_min_qty`, `product_max_qty`,
  `trigger` and `location_id`.
- With no stock and no open RFQ, `qty_to_order` equals `product_max_qty` (observed live: min 5, max 20, read 20).
- After `action_replenish`: a `purchase.order.line` for the product in `state == 'draft'` with
  `product_qty == qty_to_order` and `orderpoint_id` = the rule; its order's `partner_id` is the vendor of the
  product's `seller_ids` line (observed live with one vendor).

## Pitfalls
- **No scheduler on the demo server.** `ofa` runs Odoo with `max_cron_threads = 0`, so the daily
  `run_scheduler` never runs. An `auto` rule therefore only fires through the immediate trigger below; a scenario or
  plan must call `action_replenish` on the rule (it is a record method, so `ofa` can call it) instead of waiting.
- **Immediate auto trigger.** `stock.picking.action_confirm` calls `stock.move._trigger_scheduler`, which runs the
  `auto` rules of the products whose stock is leaving the rule's location; it is skipped when the
  `ir.config_parameter` `stock.no_auto_scheduler` is true. Creating a rule, or a receipt, does not trigger it.
- **`procurement.group` is gone in 20.0.** The scheduler entry point is `stock.rule.run_scheduler` (not
  `procurement.group.run_scheduler`), and documents are grouped through `stock.reference` (`reference_ids` on
  pickings and purchase orders).
- `qty_to_order` is not stored; read it, do not search on it in a plan.
- A product without vendors gets no RFQ: with `trigger = 'manual'` the button raises an error that opens the
  product form; with `auto`, the scheduler does not raise and logs an activity on the product template instead.
- `action_replenish` deletes `manual` rules created by the superuser whose `qty_to_order` falls to 0 afterwards
  (the replenishment report's temporary rules); rules created by a user stay.

## Alternatives
- MTO (buy per customer order) when stock should not be held.
- Purchase Agreements (blanket orders, `purchase.requisition`) to fix prices and quantities with a vendor, with the
  rule still deciding when to order.
- A periodic manual review of the replenishment report (`stock.action_orderpoint_replenish`) when lead times or
  demand are too irregular for fixed min/max values.
