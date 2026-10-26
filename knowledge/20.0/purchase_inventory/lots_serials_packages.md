---
title: Lots and serial numbers vs packages
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/stock/models/res_config_settings.py@20.0, odoo/addons/stock/models/product.py@20.0, odoo/addons/product/models/product_template.py@20.0, odoo/addons/stock/models/stock_lot.py@20.0, odoo/addons/stock/models/stock_package.py@20.0, odoo/addons/stock/models/stock_move_line.py@20.0, odoo/addons/stock/models/stock_picking.py@20.0, odoo/addons/stock/models/stock_picking_type.py@20.0, odoo/addons/stock_account/models/product.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [stock]
models: [product.template, stock.lot, stock.package, stock.package.type, stock.move.line, stock.quant, stock.picking.type, res.config.settings]
settings: [group_stock_production_lot, group_stock_tracking_lot, group_lot_on_delivery_slip, module_product_expiry]
---

## When to use
- If the business must know **which batch** a unit came from (recalls, expiry, food, chemicals, pharma), track by
  **lots** (`store_by = 'lot'`), because every receipt and delivery line then records a `stock.lot`.
- If every unit is individually identified (machines, phones, warranty by unit), track by **serial numbers**
  (`store_by = 'serial'`): one unit per serial; more than one unit of the same serial in a location makes
  `stock.quant` raise "The serial number has already been assigned".
- If the need is to group goods physically (boxes, pallets) and move or ship them as one unit, use **packages**
  (`group_stock_tracking_lot`). Packages say *where and in what container* goods are, not *which batch* they are;
  they can be combined with lots.
- If only quantities matter, keep `store_by = 'quantity'`: tracking adds a mandatory field on every operation.

## Configuration
- Settings (`res.config.settings`, `odoo/addons/stock/models/res_config_settings.py@20.0`):
  - `group_stock_production_lot` ("Lots & Serial Numbers", implies `stock.group_production_lot`).
  - `group_stock_tracking_lot` ("Packages", implies `stock.group_tracking_lot`).
  - Optional: `group_lot_on_delivery_slip` (lots printed on delivery slips), `module_product_expiry`
    ("Expiration Dates"), `group_lot_on_invoice` (from `stock_account`, lots on invoices).
- Product, **new in 20.0**: `product.template.store_by` ("Tracking", selection `untracked` "None", `quantity` "By
  Quantity", `lot` "By Lots", `serial` "By Unique Serial Number"; computed with an inverse). It drives two stored
  fields:
  - `is_storable` ("Track Inventory", only for `type = 'consu'`);
  - `tracking` (selection `lot` / `serial` only; `False` means tracked by quantity). There is no `'none'` value.
  Write `store_by` (or `is_storable` plus `tracking`) in plans.
- Lot model: `stock.lot` (`name`, `product_id`, `company_id`, `quant_ids`, `location_id`); the pair lot name +
  product is unique per company.
- Operation types: `stock.picking.type.use_create_lots` (computed true for `incoming`) and `use_existing_lots`
  (computed true for `outgoing`). A receipt creates lots from `stock.move.line.lot_name`; a delivery picks existing
  ones in `stock.move.line.lot_id`.
- Package model: **`stock.package`** in 20.0 (not `stock.quant.package`), with `name`, `package_type_id`
  (`stock.package.type`), `location_id`, `quant_ids`, and `parent_package_id` for packages inside packages. Move
  lines carry the source `package_id` and the destination `result_package_id`.
- Putting goods in a package: `stock.picking.action_put_in_pack` (also on `stock.move.line`), keyword-only
  arguments `package_id`, `package_type_id`, `package_name`.
- Valuation by lot (optional): `product.template.lot_valuated` ("Valuation by Lot/Serial", `stock_account`), only for
  lot/serial products.

## How to verify
- Settings: `base.group_user` has `stock.group_production_lot` (lots) or `stock.group_tracking_lot` (packages) in
  `implied_ids`.
- Product: `product.template.store_by` reads `lot` or `serial`; equivalently `is_storable == True` and `tracking`
  is `lot` / `serial`.
- After a receipt of a tracked product: its `stock.move.line` records have `lot_id` set, and a `stock.lot` with that
  `name` and `product_id` exists; `stock.quant` in the destination has the same `lot_id`.
- After put in pack: `stock.move.line.result_package_id` is set and, once done, `stock.quant.package_id` points to
  the `stock.package`.

## Pitfalls
- **The demo template already has Lots & Serial Numbers on.** On the 20.0 demo database `base.group_user` implies
  `stock.group_production_lot` before any plan runs, while Packages is off (observed live). A plan that enables
  lots reports `unchanged` with `pre_state: true` and proves nothing; check the pre-state, or test Packages.
- Validating a receipt of a tracked product without a lot raises "You need to supply a Lot/Serial number for
  products ..." from `stock.picking._sanity_check`; scenarios must write `lot_name` (receipts) or `lot_id`
  (deliveries) on the move lines first.
- Old names that fail in 20.0: `stock.production.lot` (now `stock.lot`), `stock.quant.package` (now
  `stock.package`), `tracking = 'none'` (now `False` / `store_by = 'quantity'`), `detailed_type = 'product'` (now
  `type = 'consu'` with `is_storable`).
- Turning lot valuation on (`lot_valuated`) raises when the product has on-hand quantities without a lot in valued
  locations.

## Alternatives
- Consignment (`group_stock_tracking_owner`) when the question is "who owns this stock", not "which batch".
- Product variants or separate products when the "batch" is really a different item (size, colour).
- Expiration dates (`module_product_expiry`) on top of lots for best-before and removal dates.
