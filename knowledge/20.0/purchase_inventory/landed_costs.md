---
title: Landed costs (freight, duties and insurance in the product cost)
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/stock_landed_costs/__manifest__.py@20.0, odoo/addons/stock_landed_costs/models/stock_landed_cost.py@20.0, odoo/addons/stock_landed_costs/models/product.py@20.0, odoo/addons/stock_landed_costs/models/account_move.py@20.0, odoo/addons/stock_landed_costs/models/res_config_settings.py@20.0, odoo/addons/stock_account/models/res_config_settings.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [stock_landed_costs, stock_account, purchase_stock]
models: [stock.landed.cost, stock.landed.cost.lines, stock.valuation.adjustment.lines, product.template, account.move, account.move.line, res.config.settings]
settings: [module_stock_landed_costs, lc_journal_id]
---

## When to use
- If imported goods carry freight, customs duties or insurance that should be part of their cost (so margins and
  stock value are right), use **landed costs**, because they spread those extra costs over the received goods.
- If the goods use **AVCO or FIFO** costing, landed costs change their unit cost. With **standard** costing they do
  not change the product cost (the product help says only AVCO/FIFO products have their value affected); then the
  cost usually belongs in the standard price instead.
- If the extra cost is small and not worth tracking per receipt, book it as a plain expense on the vendor bill.

## Configuration
- Module: `stock_landed_costs` ("WMS Landed Costs", LGPL, **Community** in 20.0, depends on `stock_account` and
  `purchase_stock`). Install it with the setting `module_stock_landed_costs` ("Landed Costs") or an
  `install_modules` op. Default journal: setting `lc_journal_id` (related `res.company.lc_journal_id`).
- Cost product: a **service** with `product.template.landed_cost_ok = True` ("Is a Landed Cost") and an optional
  `split_method_landed_cost` (default split). `landed_cost_ok` is cleared if the product stops being a service.
  `landed_cost_on_product_ids` limits which goods it applies to.
- Landed cost document `stock.landed.cost`:
  - `target_model` (`picking` "Transfers", the only value), `picking_ids` (the receipts), `cost_lines`,
    `valuation_adjustment_lines`, `vendor_bill_id`, `account_journal_id`, `state` (`draft`, `done` "Posted",
    `cancel`).
  - Cost lines `stock.landed.cost.lines`: `product_id`, `price_unit`, `split_method` (`equal`, `by_quantity`,
    `by_current_cost_price`, `by_weight`, `by_volume`), `account_id`.
  - `compute_landed_cost` fills `valuation_adjustment_lines` (`stock.valuation.adjustment.lines`: `move_id`,
    `former_cost`, `additional_landed_cost`, `final_cost`); `button_validate` computes them if missing, checks the
    totals, sets `state = 'done'`, and posts a journal entry only for products with `valuation == 'real_time'`.
- From the vendor bill: a bill line whose product has `landed_cost_ok` gets `is_landed_costs_line`; the bill button
  `account.move.button_create_landed_costs` creates a draft `stock.landed.cost` with the bill's purchase receipts as
  `picking_ids` and one cost line per landed-cost bill line.

## How to verify
- Module: `ir.module.module` `stock_landed_costs` reads `state == 'installed'`.
- Cost product: `product.template.landed_cost_ok == True`, `type == 'service'`.
- After validation: `stock.landed.cost.state == 'done'`; each `valuation_adjustment_lines` record has
  `additional_landed_cost > 0` and `final_cost = former_cost + additional_landed_cost`; `amount_total` equals the sum
  of the cost lines. For `real_time` products, `account_move_id` is set.
- Fields and selections above were read live after installing the module on a 20.0 demo DB; the validation flow is
  from source.

## Pitfalls
- **Not an Enterprise module in 20.0.** It lives in `odoo/addons/stock_landed_costs`; a Community target can use it.
- **Not installed on the demo template.** `stock_landed_costs` is uninstalled there; plan an `install_modules` op.
- `button_validate` raises "Please define Transfers on which those additional costs should apply." without
  `picking_ids`, and "Cost and adjustments lines do not match. You should maybe recompute the landed costs." when the
  adjustment lines are stale (call `compute_landed_cost` again after editing cost lines).
- A validated landed cost cannot be cancelled ("Validated landed costs cannot be cancelled, but you could create
  negative landed costs to reverse them").
- For perpetual products, a cost product without an expense account raises "Please configure Stock Expense Account
  for product: ...".

## Alternatives
- Include freight in the purchase order line price when the vendor's price is all-in.
- Standard costing with a standard price that already includes average freight and duties.
