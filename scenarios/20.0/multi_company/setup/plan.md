# Multi-company scenarios fixture: subsidiary, branch and inter-company sales orders

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise (the inter-company modules are Enterprise; the rest is community)
- Areas: multi_company
- Scenarios it supports: `scenarios/20.0/multi_company/multi_company_isolation.json`,
  `scenarios/20.0/multi_company/multi_company_intercompany_so_po.json`

## Summary
The demo template already has five companies (two in Mexico, three in the United States), all flat (no branches),
and none of the inter-company modules. A scenario built only on them would prove nothing about a plan, and the
fictional company names of the Mexican demo data should not end up in scenario files. The plan creates its own
subsidiary with a branch, a warehouse for the subsidiary, one subsidiary-only product and one shared product, and
switches on the inter-company sales order rule for the subsidiary.

## Decision 1: Inter-company modules
- Ops: [op_010_install_intercompany]
- Decision: install `account_inter_company_rules`, `sale_purchase_inter_company_rules` and
  `sale_purchase_stock_inter_company_rules` (Enterprise).
- Business reason: the subsidiary must get the sales order automatically when the main company buys from it.
- What Odoo does: adds the per-company fields `intercompany_generate_sales_orders`,
  `intercompany_generate_purchase_orders`, `intercompany_generate_bills_refund`, `intercompany_document_state`,
  `intercompany_purchase_journal_id` and `intercompany_sync_delivery_receipt` on `res.company`, and the
  `auto_generated` / `auto_purchase_order_id` fields on `sale.order`.
- Pre-state: none of the three modules is installed in the template (checked with `ofa inspect` on
  `ir.module.module`).
- Pitfalls: 20.0 has no inter-company user setting any more; the documents are created as the superuser.
- Sources: `knowledge/20.0/multi_company/intercompany_rules.md`

## Decision 2: A subsidiary with a branch
- Ops: [op_020_subsidiary_company] [op_030_subsidiary_branch]
- Decision: "OFA Subsidiary North" is a root `res.company` in the United States; "OFA North Branch" is a branch of
  it (`parent_id`).
- Business reason: the subsidiary is a separate legal entity; the regional office is part of it and should see its
  contacts and products but not its orders.
- What Odoo does: the country loads the `us` chart for the subsidiary; the branch gets the same `chart_template`
  and uses the subsidiary's journals and taxes. Odoo links both companies to the creating user (`ofa_bot`) and the
  superuser only, and `ofa apply` also adds them to the bot.
- Pre-state: neither company exists in the template.
- Pitfalls: `parent_id` can never be written again ("The company hierarchy cannot be changed."); a re-apply leaves
  it alone because the value already holds. The admin user does not get the new companies.
- Sources: `knowledge/20.0/multi_company/companies_and_branches.md`,
  `knowledge/20.0/multi_company/user_company_access.md`

## Decision 3: A warehouse for the subsidiary
- Ops: [op_040_subsidiary_warehouse]
- Decision: `stock.warehouse` "OFA North Warehouse" (code `OFAN`) in the subsidiary, created in the subsidiary's
  context.
- Business reason: the generated sales order ships from the subsidiary's own stock.
- What Odoo does: a new company gets locations and operation types but no warehouse; without one,
  `sale_purchase_stock_inter_company_rules` refuses to create the sales order.
- Pre-state: the subsidiary has no warehouse right after it is created.
- Sources: `knowledge/20.0/multi_company/companies_and_branches.md`,
  `knowledge/20.0/multi_company/intercompany_rules.md`

## Decision 4: The subsidiary generates sales orders
- Ops: [op_050_subsidiary_generate_so]
- Decision: settings field `intercompany_generate_sales_orders` = true, saved with `company` = the subsidiary.
- Business reason: the rule is set on the company that receives the purchase order.
- What Odoo does: the settings field is related to `res.company.intercompany_generate_sales_orders`, so it is per
  company; the main company and the branch keep false. `intercompany_document_state` stays `draft`, so the
  generated order waits for the subsidiary's confirmation.
- Pre-state: false on every company after the install.
- Sources: `knowledge/20.0/multi_company/intercompany_rules.md`, `knowledge/20.0/multi_company/per_company_settings.md`

## Decision 5: A subsidiary-only product and a shared product
- Ops: [op_060_subsidiary_only_product] [op_070_shared_product]
- Decision: "OFA Subsidiary-only part" has `company_id` = the subsidiary; "OFA Shared catalog part" has no
  `company_id`, a sales price of 80, and can be sold and bought.
- Business reason: the subsidiary's own products stay private; catalog parts are traded between companies.
- What Odoo does: `product.template` is visible in its company and its branches (`parent_of` rule), or everywhere
  when `company_id` is empty. A shared product gets the default taxes of every company whatever the context
  (`_force_default_tax`), so the op's `company` (the main company) does not limit them. The plan does not set
  taxes: each order line only uses the taxes of its own company.
- Pre-state: neither product exists in the template.
- Sources: `knowledge/20.0/multi_company/shared_vs_company_records.md`
<!-- ofa-lint-ignore: parent_of -->

## Not covered
- Inter-company invoices to bills (`intercompany_generate_bills_refund`) and sales orders to purchase orders
  (`intercompany_generate_purchase_orders`): same mechanism, not exercised by a scenario.
- Users restricted to one company: the scenarios use the bot user, see `multi_company_isolation`.
- Consolidated reports: no consolidation module in 20.0.
