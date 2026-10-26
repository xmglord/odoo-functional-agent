---
title: Routes - Buy, Replenish on Order (MTO) and Dropship
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/stock/models/res_config_settings.py@20.0, odoo/addons/stock/data/stock_data.xml@20.0, odoo/addons/stock/models/stock_location.py@20.0, odoo/addons/stock/models/stock_rule.py@20.0, odoo/addons/stock/models/stock_warehouse.py@20.0, odoo/addons/purchase_stock/data/purchase_stock_data.xml@20.0, odoo/addons/purchase_stock/models/stock.py@20.0, odoo/addons/stock_dropshipping/data/stock_data.xml@20.0, odoo/addons/stock_dropshipping/models/stock.py@20.0, odoo/addons/sale_stock/models/sale_order_line.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [stock, purchase_stock, sale_stock, stock_dropshipping]
models: [stock.route, stock.rule, stock.warehouse, product.template, sale.order.line, stock.picking.type, stock.picking, res.config.settings]
settings: [replenish_on_order, module_stock_dropshipping]
---

## When to use
- If a product is bought from a vendor to refill stock, nothing is needed on the product: the warehouse's **Buy**
  route (`buy_to_resupply`, on by default) applies to every product that has a vendor (`seller_ids`).
- If a product is bought (or made) only when a customer orders it (custom or expensive items, no safety stock), add
  **Replenish on Order (MTO)** to the product, because confirming the sales order then creates the purchase need
  for exactly that quantity instead of waiting for stock.
- If the vendor ships straight to the customer and the goods never enter the warehouse, use **Dropship**
  (`module_stock_dropshipping`), because the purchase order then creates a Vendors-to-Customers transfer and no
  receipt or delivery in the warehouse.
- If the choice is per order rather than per product (dropship only large orders), set the route on the sales order
  line instead of the product.

## Configuration
- Route model `stock.route` (defined in `odoo/addons/stock/models/stock_location.py@20.0`) with flags
  `product_selectable`, `product_categ_selectable`, `warehouse_selectable`, `sale_selectable`, and `rule_ids`
  (`stock.rule`, `action` in `pull` / `push` / `pull_push` / `buy`, `procure_method` in `make_to_stock` /
  `make_to_order` / `mts_else_mto`).
- **Buy** (`purchase_stock.route_warehouse0_buy`): `product_selectable = False`, `warehouse_selectable = True`. It is
  switched per warehouse with `stock.warehouse.buy_to_resupply` (default true; rule `buy_pull_id`). It is not
  ticked on products in 20.0.
- **MTO** (`stock.route_warehouse0_mto`, "Replenish on Order (MTO)"): archived by default. The setting
  `replenish_on_order` ("Replenish on Order (MTO)") is computed from that route's `active` flag and its inverse
  writes it. Each warehouse's MTO rule is `stock.warehouse.mto_pull_id`. Then add the route to the product:
  `product.template.route_ids` (domain `product_selectable = True`).
- **Dropship**: setting `module_stock_dropshipping` installs `stock_dropshipping`, which creates the route
  `stock_dropshipping.route_drop_shipping` (product- and sale-selectable) and, per company, an operation type with
  `code = 'dropship'` (Vendors to Customers). Pickings get the computed `is_dropship`.
- Per-order routes: `sale.order.line.route_ids` (many2many, domain `sale_selectable = True`).
- Rule choice (`stock.rule._search_rule_for_warehouses`): candidates come from the line's routes, the package type,
  the product and its category, and the warehouse; the rule of the route with the lowest `sequence` wins (MTO 5,
  Buy 10, Dropship 20 in the shipped data).

## How to verify
- Buy: `stock.warehouse.buy_to_resupply == True` and the product has at least one `seller_ids` line
  (`product.supplierinfo.partner_id`).
- MTO: `stock.route_warehouse0_mto` reads `active == True`; the product's `route_ids` contains it. After a sales order
  for the product is confirmed, a draft `purchase.order.line` exists for that product.
- Dropship: `stock_dropshipping` is `installed`; a `stock.picking.type` with `code == 'dropship'` exists for the
  company; after the purchase order of a dropship sale is confirmed, its picking reads `is_dropship == True` with
  `location_id` = Vendors and `location_dest_id` = Customers.

## Pitfalls
- **The Buy route is not on products any more.** Writing `purchase_stock.route_warehouse0_buy` into
  `product.template.route_ids` fails with "Cannot link inaccessible records in product.template.route_ids
  ([('product_selectable', '=', True)])" (observed live). Configure `buy_to_resupply` on the warehouse and vendors on
  the product.
- **`sale.order.line.route_id` does not exist in 20.0**; the field is `route_ids` (many2many).
- **MTO is archived on a new database.** The route can still be linked to a product while it is archived (observed
  live), but archiving a route archives its rules (`stock.route.write`), so it fulfils nothing. Enable `replenish_on_order` first and read the
  route's `active` back.
- An MTO product without a vendor (and without manufacturing) has no rule for the need: `sale.order.action_confirm`
  raises `UserError` "No rule has been found to replenish ... Verify the routes configuration on the product."
  (observed live). With a vendor, confirmation creates a draft purchase order line for the ordered quantity
  (observed live).
- Dropship requires `sale_purchase_stock` (the module depends on it); the operation type code is `dropship`, not
  `incoming` as in older versions.
- `mts_else_mto` ("Take From Stock, if unavailable, Trigger Another Rule") exists on rules; it is set on the rule,
  not through a product setting.

## Alternatives
- Reordering rules (see the reordering rules entry) when buying for stock against a minimum rather than per order.
- A rule with `procure_method = 'mts_else_mto'` when stock should be used first and purchased only for the
  shortfall.
- Manual purchase orders from the sales order when exceptions are rare.
