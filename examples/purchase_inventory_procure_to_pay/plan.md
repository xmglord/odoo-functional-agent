# Harbor Fresh: purchase to vendor bill with replenishment, two-step receipts, FEFO and 3-way matching

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise
- Areas: purchase_inventory, accounting
- Company: "My Company (San Francisco)" (`base.main_company`, USD, 15% purchase tax), main warehouse `stock.warehouse0` (code WH)

## Summary
A food and cleaning-supplies distributor wants control from the purchase order to the vendor bill. The plan turns on
purchase approval above 50,000, records each vendor's price, minimum quantity and lead time per product, adds an
automatic min/max reordering rule, switches the warehouse to two-step receipts with automatic backorders, tracks food
by lot with expiry dates and FEFO picking, bills on received quantities, and installs 3-way matching so Accounts
Payable sees quantity and price differences on bills. Two parts of the requirement are not exactly reachable by
configuration (before-tax threshold, cheapest vendor across vendors); the user accepted the compromises below.

## Decision 1: Purchase approval at 50,000
- Ops: [op_020_po_approval]
- Decision: enable Purchase Order Approval with a minimum amount of 50,000 on the main company.
- Business reason: requirement 1. Orders at or above the amount stop in state `to approve` after the buyer confirms,
  and are sent to the vendor only after a purchase manager presses "Approve Order".
- What Odoo does:
  - settings: `po_order_approval` writes `res.company.po_double_validation` = `two_step`; `po_double_validation_amount`
    is the threshold (company currency).
  - `purchase.order.button_confirm` moves the order to `to approve` unless `_approval_allowed` holds: one-step
    company, `purchase.order.amount_total` below the threshold, or the user has `purchase.group_purchase_manager`.
  - `purchase.order.button_approve` is the manager's approval.
  - menu path: Purchase > Configuration > Settings > Orders > Purchase Order Approval
- Deviation (accepted by the user): Odoo compares the threshold with `amount_total`, which **includes tax**; there is
  no before-tax option. At 15% tax, an order of about 43,479 before tax already needs approval. This is stricter
  than asked, never looser. A threshold of 57,500 was rejected because 0%-tax food lines would slip through.
- "Any buyer can create purchase orders": standard `purchase.group_purchase_user` rights; nothing to configure.
- Pre-state: template is `one_step` with 5,000 (checked with `ofa inspect --target t24 res.company`), so this is a
  real change.
- Alternatives: Studio approval rules (`web_studio`, not installed) could test `amount_untaxed`, but they are
  enforced by the web client on button clicks, so they are harder to prove and add a module; not chosen.
- Pitfalls: managers bypass the threshold; turning approval off does not release orders already in `to approve`.
- Sources: `knowledge/20.0/purchase_inventory/purchase_approval.md`

## Decision 2: Vendor price lists per product, native vendor choice
- Ops: [op_090_vendor_bayline] [op_100_vendor_northpoint] [op_110_vendor_coastal] [op_120_vendor_clearwave] [op_130_vendor_brightside] [op_200_price_tomatoes_bayline] [op_210_price_tomatoes_northpoint] [op_220_price_tomatoes_coastal] [op_230_price_cleaner_clearwave] [op_240_price_cleaner_brightside] [op_250_price_soap_clearwave]
- Decision: five fictional vendors and one `product.supplierinfo` line per vendor and product, with `price`,
  `min_qty`, `delay` (lead time in days) and the same `sequence` (10) on every line.
- Business reason: requirement 2. These lines are what Odoo uses to propose a vendor and price.
- What Odoo does (checked in the 20.0 source, `product.product._prepare_sellers` and `_select_seller`):
  1. drop lines whose `min_qty` is above the quantity, or out of their date range;
  2. sort the rest by `sequence`, then **`min_qty` descending**, then `price`; the first line's vendor wins;
  3. among that vendor's lines, take the cheapest.
  The proposal is used by reordering rules (`stock.warehouse.orderpoint.effective_vendor_id` and the RFQ they
  create) and by the replenishment report. On a purchase order a buyer creates by hand, the buyer picks the vendor
  and Odoo fills that vendor's price for the quantity (`purchase.order.line.price_unit`).
- Deviation (accepted by the user): Odoo proposes the vendor with the **largest quantity break the order reaches**,
  not the cheapest. With equal sequence this is the cheapest whenever bigger breaks are cheaper (the usual case).
  Demo data includes a counter-example on purpose: tomatoes at 600 units go to Coastal (1.10, min 500) although
  Northpoint (1.00, min 100) is cheaper. Buyers can override with `sequence` per product, or set
  `stock.warehouse.orderpoint.supplier_id` on a rule.
- Demo data (fictional):

  | Product | Vendor | Price | Min qty | Lead time |
  |---|---|---|---|---|
  | Canned Diced Tomatoes 400 g (HF-FD-001) | Bayline Foods Supply | 1.20 | 1 | 3 days |
  | | Northpoint Wholesale Grocers | 1.00 | 100 | 7 days |
  | | Coastal Pantry Traders | 1.10 | 500 | 5 days |
  | Floor Cleaner Concentrate 5 L (HF-CL-001) | Clearwave Janitorial Co. | 9.00 | 1 | 2 days |
  | | Brightside Cleaning Supply | 7.50 | 50 | 6 days |
  | Dish Soap 5 L (HF-CL-002) | Clearwave Janitorial Co. | 6.00 | 1 | 2 days |

- Pre-state: none of these records exist in the template.
- Alternatives: Purchase Agreements (`purchase_requisition`, blanket orders) when prices are negotiated per period;
  a customization of `_select_seller` for a true "cheapest across vendors" rule.
- Pitfalls: `sequence` dominates everything; a new vendor line created from the UI gets the default sequence, so
  keep it consistent or the ranking changes silently.
- Sources: `knowledge/20.0/purchase_inventory/reordering_rules.md` (vendor lines); the selection order is uncited:
  no compendium entry, read from the 20.0 source and checked with
  `ofa inspect --target t24 product.supplierinfo --fields partner_id,price,min_qty,delay,sequence`.

## Decision 3: Automatic min/max replenishment
- Ops: [op_300_reorder_floor_cleaner]
- Decision: an automatic reordering rule (`trigger` = `auto`) for the fast-moving floor cleaner in WH/Stock, min 20,
  max 100.
- Business reason: requirement 3. When the forecast drops below 20, Odoo creates or extends a draft RFQ (a purchase
  order in state `draft`) for the proposed vendor with quantity `max - forecast`, linked to the rule
  (`purchase.order.line.orderpoint_id`). The buyer reviews and confirms it.
- What Odoo does:
  - `stock.warehouse.orderpoint`: `product_min_qty`, `product_max_qty`, `trigger`, `location_id`; read-only
    `qty_to_order` and `effective_vendor_id`.
  - Vendor and route: the warehouse Buy route (`stock.warehouse.buy_to_resupply`, already on) and Decision 2's vendor
    lines; no route on the product.
  - Two triggers: the daily scheduler (`stock.rule.run_scheduler`) and an immediate one when an outgoing transfer is
    confirmed (`stock.move._trigger_scheduler`).
  - menu path: Inventory > Operations > Replenishment
- Pre-state: no rule exists.
- Alternatives: `trigger` = `manual` if buyers want to press "Order" themselves in the replenishment report.
- Pitfalls: the demo server runs without cron, so only the immediate trigger can be tested; forecast counts draft
  RFQs, so a second drop does not double-order. Other fast movers need their own rule (data entry, one per product).
- Sources: `knowledge/20.0/purchase_inventory/reordering_rules.md`

## Decision 4: Two-step receipts with automatic backorders
- Ops: [op_030_multi_step_routes] [op_050_warehouse_two_steps] [op_060_receipt_backorder_always]
- Decision: turn on Storage Locations and Multi-Step Routes, set the main warehouse to "Receive then Store", and set
  the Receipts operation type to always create a backorder.
- Business reason: requirement 4. Goods land in WH/Input (the dock) through the receipt; validating it creates a
  storage transfer to WH/Stock (the shelf). A partial delivery is validated as received and the missing quantity
  stays open in a backorder on the **same** purchase order (`stock.picking.backorder_id`, `purchase_id`), never a
  new order. `always` removes the "No Backorder" choice so pending quantities are not cancelled by mistake.
- What Odoo does:
  - settings: `group_stock_multi_locations`, `group_stock_adv_location` (both set: a plan runs no onchange).
  - `stock.warehouse.reception_steps` = `two_steps`; `stock.warehouse.store_type_id` becomes active.
  - `stock.picking.type.create_backorder` = `always` on `stock.picking_type_in`.
  - "Receive things we never ordered": receipts come from confirmed purchase orders, and the bill follows the
    received quantity (Decision 6); nothing else to configure.
  - menu path: Inventory > Configuration > Warehouses > YourCompany > Incoming Shipments
- Pre-state: Multi-Step Routes off, warehouse `one_step`, `create_backorder` = `ask` (checked with `ofa inspect`).
- Alternatives: keep `ask` if the warehouse must sometimes cancel the rest; three steps if a quality check is needed.
- Pitfalls: `purchase.order.line.qty_received` rises at the dock step, before put-away, so "received" means "at the
  dock". The storage transfer is not linked to the purchase order; find it from the receipt's moves.
- Sources: `knowledge/20.0/purchase_inventory/multi_step_routes.md`, `knowledge/20.0/purchase_inventory/backorders.md`

## Decision 5: Lots with expiry dates and FEFO picking for food
- Ops: [op_010_install_product_expiry] [op_040_lots] [op_070_categ_food] [op_080_categ_cleaning] [op_140_product_tomatoes]
- Decision: install Expiration Dates, keep Lots on, create a "Food" category whose removal strategy is FEFO, and set
  food products to lot tracking with `use_expiration_date`.
- Business reason: requirement 5. The receiver records lot and expiry date on each receipt line
  (`stock.move.line.lot_name`, `stock.move.line.expiration_date`), which become `stock.lot.expiration_date`. When a
  delivery reserves stock, FEFO orders quants by `removal_date` (equal to the expiry date here, `removal_time` 0),
  so the earliest-expiring lot goes out first.
- What Odoo does:
  - module `product_expiry` adds `product.template.use_expiration_date`, `product.template.expiration_time` (default
    expiry in days, 540 here, editable per lot at receipt) and the removal strategy `product_expiry.removal_fefo`.
  - `product.category.removal_strategy_id` = FEFO on Food; `product.template.store_by` = `lot`.
  - Cleaning supplies get their own category with no removal strategy (warehouse default FIFO) and no tracking.
  - menu path: Inventory > Configuration > Product Categories > Food > Force Removal Strategy
- Pre-state: Lots & Serial Numbers is **already on** in the template, so [op_040_lots] will report `unchanged` with
  `pre_state: true` and proves nothing; it stays in the plan to document the dependency. `product_expiry` is not
  installed.
- Alternatives: FEFO on the WH/Stock location (`stock.location.removal_strategy_id`) instead of the category, if
  every product in the warehouse should follow it.
- Pitfalls: a lot without expiry date sorts last under FEFO; receipts of a lot product cannot be validated without a
  lot. Other food products must be put in the Food category to inherit FEFO.
- Sources: `knowledge/20.0/purchase_inventory/lots_serials_packages.md`; FEFO and expiry fields uncited: no
  compendium entry, names read from `product_expiry` 20.0 source and to be confirmed after install.

## Decision 6: Bills on received quantities with 3-way matching
- Ops: [op_015_install_3way_match] [op_150_product_floor_cleaner] [op_160_product_dish_soap]
- Decision: every product bills on received quantities (`product.template.purchase_method` = `receive`), and the
  Enterprise module "Vendor Bill: Release to Pay" (`account_3way_match`) is installed.
- Business reason: requirement 6. A bill created from the purchase order only carries what was received
  (`purchase.order.line.qty_to_invoice` = received - billed). Each bill line gets `account.move.line.can_be_paid`
  and the bill `account.move.release_to_pay`: `yes` when billed quantity ≤ received and the price equals the order
  price, `exception` when the vendor bills more than received or a different price, `no` when nothing is received.
  Accounts Payable filters on "Should Be Paid" (`account.move.release_to_pay_manual`) before validating and paying.
- What Odoo does: `purchase.order.action_create_invoice` creates the draft bill; `account.move.action_post` validates.
- Limitation: Release to Pay **flags** a bill; it does not technically block posting or registering a payment. The
  control is AP working from the "Should Be Paid" status. A hard block needs a customization.
- Pre-state: `account_3way_match` not installed; products are new.
- Alternatives: ordered-quantity billing (`purchase`) only for services or prepaid goods.
- Pitfalls: a draft bill already counts in `purchase.order.line.qty_invoiced`, so a second bill for the same lines
  turns into `exception`; bills need a bill date (`account.move.invoice_date`) to post.
- Sources: `knowledge/20.0/purchase_inventory/bill_control.md`

## Test plan
Scenarios run as `ofa_bot` in company `base.main_company`, in this order (later ones share products with earlier ones).

| Need (from requirement.md) | Scenario | What it checks |
|---|---|---|
| 1. Orders ≥ 50,000 need manager approval | hf_po_approval | `res.company.po_double_validation` = `two_step`, `po_double_validation_amount` = 50000. **Behaviour (state `to approve`) Not tested**: `ofa_bot` is a purchase manager and bypasses the threshold; check it by hand as a buyer-only user. |
| 2. Vendor price, min qty and lead time per product; propose cheapest vendor that can deliver | hf_vendor_proposal | supplierinfo lines read back (price, min_qty, delay). A temporary manual rule on tomatoes: `effective_vendor_id` = Bayline at 50 units, Northpoint at 200, Coastal at 600 (the documented counter-example, not the cheapest). "Order Once" (`action_replenish`) at 200 makes a draft RFQ to Northpoint with `price_unit` 1.00, `product_qty` 200. Rule archived at the end. |
| 3. Below min, an RFQ to the proposed vendor up to max is prepared automatically | hf_auto_replenishment | rule reads min 20, max 100, `trigger` `auto`, `effective_vendor_id` Brightside. Confirm a delivery of 10 floor cleaners (stock 0): a draft `purchase.order.line` with `orderpoint_id` = the rule, `product_qty` 110, `price_unit` 7.50, order `partner_id` Brightside, `state` `draft`. |
| 4. Two-step receipt; partial delivery leaves the rest pending on the same order | hf_receive_partial_and_bill | PO of 10 dish soap: receipt goes to WH/Input; 6 received and validated with no wizard; exactly one backorder with 4 units and `purchase_id` = same PO; storage transfer from the receipt validated; `stock.quant` in WH/Stock = 6; PO `receipt_status` `partial`. |
| 5. Lot + expiry at receipt; FEFO at picking | hf_lots_fefo | two POs of 20 tomatoes, later-expiring lot received first (HF-LATE, 2028-06-30), then HF-EARLY (2027-03-31), both put away; `stock.lot.expiration_date` read back on both; a delivery of 10 reserves `lot_id` = HF-EARLY (FIFO would have picked HF-LATE). |
| 6a. Bill only for received quantity | hf_receive_partial_and_bill | after receiving 6 of 10: `qty_to_invoice` 6; the bill from the PO has line `quantity` 6; `release_to_pay` `yes`; posts. |
| 6b. Price or over-quantity difference visible to AP | hf_receive_partial_and_bill | the same bill with `price_unit` changed to 6.50 reads `release_to_pay` `exception`, back to `yes` at 6.00; a second bill for 4 more units (10 billed vs 6 received) reads `exception`. |
| 6c. Payment blocked until received | **Not tested** | Odoo does not block payment; Release to Pay is a status AP filters on (see Decision 6). |

## Not covered by this plan
- Before-tax approval threshold and "cheapest across vendors": not reachable by configuration; accepted deviations
  (Decisions 1 and 2).
- Hard block of payment for bills in `exception`: needs a customization.
- Buyer and manager user accounts and their access groups (`purchase.group_purchase_user`,
  `purchase.group_purchase_manager`): set per real user in Settings > Users; not created here.
- Remaining products and vendors (about 30 vendors): data import, not configuration. New food products must use the
  Food category and lot tracking; every fast mover needs its own reordering rule.

## Glossary
- **RFQ**: a draft purchase order (`purchase.order`, state `draft`) not yet confirmed.
- **Vendor price list line**: price, minimum quantity and lead time of one vendor for one product (`product.supplierinfo`).
- **Reordering rule**: min/max stock rule that creates RFQs (`stock.warehouse.orderpoint`).
- **Backorder**: a transfer holding the quantity still expected after a partial receipt (`stock.picking.backorder_id`).
- **FEFO**: First Expiry, First Out removal strategy (`product.removal`, method `fefo`).
- **3-way matching**: comparing order, receipt and bill before paying (`account.move.release_to_pay`).
