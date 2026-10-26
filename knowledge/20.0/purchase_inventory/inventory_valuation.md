---
title: Inventory valuation (periodic vs perpetual) and costing methods
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/product.py@20.0, odoo/addons/account/models/account_move_line.py@20.0, odoo/addons/stock_account/models/res_company.py@20.0, odoo/addons/stock_account/models/product.py@20.0, odoo/addons/stock_account/models/product_value.py@20.0, odoo/addons/stock_account/models/stock_move.py@20.0, odoo/addons/stock_account/models/stock_location.py@20.0, odoo/addons/account/data/service_cron.xml@20.0, enterprise/account_accountant/models/res_config_settings.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account, stock_account]
models: [res.company, product.category, product.template, stock.move, product.value, stock.location, res.config.settings]
settings: [valuation_method, cost_method, inventory_period, stock_valuation_account_id]
---

## When to use
- If the accountant books stock once per period from an inventory valuation report (small companies, simple
  bookkeeping), keep **periodic** valuation (`inventory_valuation = 'periodic'`, the default), because no journal
  entry is created per stock move; a closing entry is posted at period end.
- If the balance sheet must show stock value continuously, use **perpetual** (`real_time`, labelled "Perpetual (at
  invoicing)"). In 20.0 the entries come from billing and invoicing: the category help says "An accounting entry is
  automatically created to value the inventory when a product is billed or invoiced", and vendor bill lines of such
  products are redirected to the stock valuation account (`account.move.line._use_inventory_valuation`).
- Costing method:
  - **Standard** (`standard`, default) if the company fixes a cost per product and wants price differences shown
    separately.
  - **Average** (`average`, AVCO) if purchase prices change and the cost should follow them smoothly.
  - **FIFO** (`fifo`, added by `stock_account`) if the cost of each unit sold must be the cost of the oldest units
    in stock.
- If products need different methods, set them per product category; the company values are the defaults.

## Configuration
- **20.0 moved the defaults to the company.** `res.company` (`odoo/addons/account/models/company.py@20.0`):
  - `inventory_valuation`: `periodic` "Periodic (at closing)" (default) / `real_time` "Perpetual (at invoicing)".
  - `cost_method`: `standard` (default) / `average`, plus `fifo` from `stock_account`.
  - `inventory_period`: `manual` (default) / `daily` / `monthly`, used by the cron `account.ir_cron_post_stock_valuation`
    (`_cron_post_stock_valuation`) to post periodic closings automatically.
  - `account_stock_valuation_id`, `account_stock_journal_id`: default valuation account and journal.
- Settings fields exist only with Enterprise `account_accountant`
  (`enterprise/account_accountant/models/res_config_settings.py@20.0`): `valuation_method` (related
  `company_id.inventory_valuation`), `cost_method`, `inventory_period`, `stock_valuation_account_id`,
  `stock_journal_id`. On Community, write the `res.company` fields.
- Per category (`product.category`, company-dependent): `property_valuation` (same two values),
  `property_cost_method` (same three values, default from the company), `property_stock_valuation_account_id`,
  `property_stock_journal`, `property_price_difference_account_id`. An empty category value falls back to the company.
- Per product (read-only, computed): `product.template.valuation` and `cost_method`.
- Where values live: `stock.move.value` (monetary, with `value_justification` for FIFO), `remaining_qty` /
  `remaining_value`, and `account_move_id` for perpetual entries; manual cost changes are `product.value` records
  (`product_id`, `lot_id`, `move_id`, `value`, `old_cost` / `new_cost`). Locations decide what is valued
  (`stock.location.is_valued`, optional `valuation_account_id`).
- A stock move creates its own journal entry only when the product is storable, the move is valued, one of its
  locations has a `valuation_account_id` (help: "Expense account used to re-qualify products removed from stock and
  sent to this location"), and `product.valuation == 'real_time'` (`stock.move._should_create_account_move`). On
  the demo DB, Vendors, `WH/Input` and `WH/Stock` have no `valuation_account_id` (observed live), so a receipt
  creates no entry by itself.

## How to verify
- Company: `res.company.inventory_valuation`, `cost_method`, `inventory_period` hold the requested values.
- Category exceptions: `product.category.property_valuation` / `property_cost_method` on the named categories.
- Product: `product.template.cost_method` and `valuation` read back the effective method.
- After a receipt: the done incoming `stock.move.value` is set. Observed live on a `standard` product with cost 2.0
  bought at 3.0: the receipt move (5 units) read `value` 15.0 and the following internal storage move 0.0.
- On the 20.0 demo DB, the company is `periodic` / `standard` and every category reads `periodic` / `standard`
  (observed live): applying those values is a pre-state.

## Pitfalls
- **`stock.valuation.layer` does not exist in 20.0** (checked live). Older guides read valuation from layers; in
  20.0 read `stock.move.value` / `remaining_value` and `product.value`.
- **`manual_periodic` is gone.** `property_valuation` is `periodic` or `real_time` only, and `real_time` no longer
  means "an entry per stock move" (see Configuration).
- Changing the company `cost_method` or a category's `property_cost_method` revalues the affected products from the
  last closing date (`_correct_inventory_valuation`); do it before stock moves exist when possible.
- Do not expect a journal entry per receipt or delivery under perpetual valuation: check the vendor bill's lines
  (account = the stock valuation account) instead of `stock.move.account_move_id`.
- With `max_cron_threads = 0` on the demo server, `inventory_period = 'daily'` or `'monthly'` never posts a closing;
  `res.company.action_close_stock_valuation` does it on demand.

## Alternatives
- Periodic valuation with a manual closing each month when the accountant prefers one adjustment entry.
- Landed costs (see the landed costs entry) to add freight and duties to the value of AVCO/FIFO products.
