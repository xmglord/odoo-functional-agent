# Plan: two-step receipts for the purchase_inventory scenarios

This fixture prepares a fresh demo database so the three scenarios of `scenarios/20.0/purchase_inventory/` can run.

- [op_010_install_purchase_stock] installs Purchase, Inventory and `purchase_stock`. On the 20.0 demo template these
  modules are already installed, so the first apply reports `unchanged` with `pre_state: true`: that result proves
  nothing about the plan, it only guards a template without them.
- [op_020_multi_step_routes] turns on Multi-Step Routes (`group_stock_adv_location`). The settings screen switches on
  Storage Locations (`group_stock_multi_locations`) through an onchange, which a plan does not run, so both are set.
  Both are off on the demo template, so this is a real change.
- [op_030_main_warehouse_two_steps] adopts the demo main warehouse (`stock.warehouse0`) under the key
  `pi_main_warehouse` and sets `reception_steps = 'two_steps'`. Receipts from purchase orders then go to `WH/Input`,
  and validating them creates a storage transfer to `WH/Stock`.

Not configured on purpose: the receipt operation type keeps its default `create_backorder = 'ask'`; the backorder
scenario checks it in a precondition instead of setting it, so the scenario proves the default wizard path.
Bill control needs no setting: in 20.0 it is a product field (`purchase_method`) that the scenarios set on their own
products.
