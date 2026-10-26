# Purchase and Inventory (20.0)

Everything from the request for quotation to goods on the shelf and the vendor bill: purchase orders and their
approval, bill control, warehouses and their receipt and delivery steps, routes (Buy, MTO, Dropship), reordering
rules, product tracking (lots, serial numbers, packages), backorders, and how stock is valued. Vendor bills are
described here only as far as purchase orders create them; see the accounting area for the rest.

| Entry | Use it when the requirement mentions |
|---|---|
| [Purchase order approval levels and order locking](purchase_approval.md) | manager approval above an amount, double validation, locking confirmed orders |
| [Bill control (ordered vs received quantities)](bill_control.md) | pay only what arrived, bills from purchase orders, 3-way matching |
| [Multi-step receipts and deliveries](multi_step_routes.md) | dock/input area, put-away, quality step, pick-pack-ship |
| [Routes: Buy, Replenish on Order (MTO) and Dropship](routes_mto_dropship.md) | buy per customer order, vendor ships to customer, which route a product follows |
| [Reordering rules and the stock scheduler](reordering_rules.md) | minimum stock, automatic RFQs, replenishment report |
| [Lots and serial numbers vs packages](lots_serials_packages.md) | batch traceability, recalls, unique serials, boxes and pallets |
| [Inventory valuation and costing methods](inventory_valuation.md) | periodic vs perpetual, standard/AVCO/FIFO, stock value in accounting |
| [Landed costs](landed_costs.md) | freight, customs duties, insurance in the product cost |
| [Backorders on partial receipts and deliveries](backorders.md) | partial deliveries, remaining quantities, cancel the rest |

Scenarios for this area live in `scenarios/20.0/purchase_inventory/`: `purchase_po_to_bill` (PO, receipt, vendor
bill on received quantities, post), `inventory_two_step_receipt` (receipt into Input, then storage into Stock) and
`inventory_partial_receipt_backorder` (receive 6 of 10, backorder wizard with `process`, backorder of 4). They need
the fixture plan in `scenarios/20.0/purchase_inventory/setup/` (Multi-Step Routes on, main warehouse in two-step
receipts) applied first.

Notes for the 20.0 version of this area (all checked against the source, most also live):

- Landed costs (`stock_landed_costs`) is a Community module in 20.0, not Enterprise.
- Old names that do not exist in 20.0: `procurement.group`, `stock.quant.package` (now `stock.package`),
  `stock.production.lot` (now `stock.lot`), `stock.valuation.layer`, `sale.order.line.route_id` (now `route_ids`),
  the settings field `default_purchase_method`, `tracking = 'none'`.
- The Buy route is warehouse-level (`stock.warehouse.buy_to_resupply`) and cannot be put on products.
- Valuation defaults (`inventory_valuation`, `cost_method`) live on `res.company`; the settings fields for them
  come from Enterprise `account_accountant`.

## Upkeep log

| Entry | Agent time: tokens | Agent time: minutes | Author review (min) |
|---|---|---|---|
| purchase_approval.md | 6,202 | 0.6 | |
| bill_control.md | 9,790 | 1.0 | |
| multi_step_routes.md | 5,742 | 0.5 | |
| routes_mto_dropship.md | 14,706 | 1.4 | |
| reordering_rules.md | 10,277 | 1.3 | |
| lots_serials_packages.md | 8,943 | 0.8 | |
| inventory_valuation.md | 13,147 | 1.4 | |
| landed_costs.md | 8,469 | 0.7 | |
| backorders.md | 6,817 | 0.6 | |
| overhead | 262,048 | 14.3 | |

Agent time is measured from the authoring agent's session transcript, between markers it printed before and after each entry. Tokens are the new tokens of its API calls in that window (input, cache writes and output); re-reads of already cached context are excluded, because every call re-reads the whole conversation (22.5 M such tokens over the session, 98% of the raw total). Overhead is the shared research before the first entry plus the index and the scenarios. Author review is minutes the author spent checking the entry.
