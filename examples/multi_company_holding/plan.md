# Ridgeline group: three companies, a branch, inter-company trade and group reporting

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise
- Areas: multi_company, accounting, sales_crm, purchase_inventory

## Summary
Ridgeline moves three legal entities into one database. Holdings, Foods and Logistics each become a root company
with its own US chart. Foods' Riverside site becomes a branch of Foods with its own warehouse and invoice journal.
Products, customers and vendors are shared records with per-company values. The Enterprise inter-company rules
mirror the haul purchase orders and the inter-company invoices. The monthly management fee is a recurring invoice
(`auto_post` monthly) in Holdings. A fourth company, Ridgeline Eliminations, holds the
monthly elimination entries, so the group P&L and balance sheet are the reports run with every company selected.
The group controller is a Bookkeeper in every company. A record restriction stops the controller from creating,
changing or deleting journal entries outside an allow-list that leaves Logistics out.

## Decision 1: Install Accounting and the inter-company rules
- Ops: [op_010_install_modules]
- Decision: install `accountant` (full Accounting, which brings `account_reports`), `account_inter_company_rules`,
  `sale_purchase_inter_company_rules` and `sale_purchase_stock_inter_company_rules`.
- Business reason: needs 3 (Bookkeeper role, multi-company reports), 4 and 5 (mirrored documents), 6 (reports).
- What Odoo does:
  - `accountant` adds the "Bookkeeper" meaning of `account.group_account_user` and makes `account.group_account_manager`
    imply it; `account_reports` (already installed) provides the P&L and balance sheet.
  - the inter-company modules add the per-company settings used in Decision 7.
- Pre-state: `account_reports`, `sale_management`, `purchase`, `sale_stock`, `purchase_stock` and `l10n_us` are
  installed in the template; `accountant` and the three inter-company modules are not (`ofa inspect` on
  `ir.module.module`).
- Alternatives: the Invoicing app alone has no Bookkeeper role and no Enterprise financial reports.
- Pitfalls: installing `accountant` changes payment behaviour (payments stay `in_payment` until bank reconciliation).
- Sources: `knowledge/20.0/accounting/invoicing_vs_accounting_apps.md`, `knowledge/20.0/multi_company/intercompany_rules.md`

## Decision 2: Three legal companies plus an eliminations company
- Ops: [op_020_company_holdings] [op_030_company_foods] [op_040_company_logistics] [op_050_company_eliminations]
- Decision: one root `res.company` per legal entity (no `parent_id`), country United States, with fictional tax IDs
  in `res.company.vat`. Ridgeline Eliminations is a fourth root company with no tax ID, used only for consolidation
  entries.
- Business reason: need 1. Each entity files its own taxes and has its own books, so each gets its own chart,
  taxes, journals (including its bank journal) and document numbering. Need 6 (Eliminations company, as agreed).
- What Odoo does:
  - `res.company.create` with `country_id` runs `install_l10n_modules` and loads the `us` chart
    (`res.company.chart_template` = `us`), creating that company's accounts, taxes and journals (Sales, Purchases,
    Bank, Cash, Miscellaneous).
  - `ofa apply` adds each new company to `ofa_bot`; nobody else gets it (the admin will not see them in the UI
    until someone adds them to the admin's `res.users.company_ids`).
- Pre-state: no company with these names exists; the template's five demo companies are left alone.
- Alternatives: branches of Holdings would share one chart and one tax ID, which contradicts "each files its own
  taxes"; separate databases would make inter-company flows and group reports impossible.
- Pitfalls: the hierarchy cannot be changed after creation (`UserError` "The company hierarchy cannot be changed.").
  Each bank account is added later as a bank journal of its company (real bank data is out of scope here).
- Sources: `knowledge/20.0/multi_company/companies_and_branches.md`, `knowledge/20.0/accounting/chart_of_accounts.md`

## Decision 3: Riverside is a branch of Foods with its own warehouse and invoice journal
- Ops: [op_060_branch_riverside] [op_080_warehouse_branch] [op_100_journal_branch_sales] [op_070_warehouse_foods]
- Decision: "Ridgeline Foods Riverside Branch" is a `res.company` with `parent_id` = Foods and the same `vat` as
  Foods. It owns the warehouse "Foods Riverside Warehouse" (code RFR) and a sales journal "Riverside Branch
  Invoices" (code RVINV, `sequence` 1). Foods owns "Foods Main Warehouse" (RFM).
- Business reason: need 1. The branch shares Foods' tax ID and books but its invoices must be identifiable and its
  stock separate.
- What Odoo does:
  - a branch loads only company-level chart data and uses Foods' accounts, taxes and journals
    (`account.journal` rule `company_id parent_of company_ids`).
  - `account.move.company_id` of an invoice created in the branch is the branch (`_compute_company_id`).
  - the default journal is the first `sale` journal visible to the branch, ordered by `sequence`
    (`_search_default_journal`). With `sequence` 1 the branch's RVINV journal comes before Foods' own, so branch
    invoices are numbered RVINV/... and land in the same books. Foods users cannot see the branch journal
    (`parent_of` only looks up the hierarchy), so Foods' own invoices keep Foods' journal.
  - `res.company.vat` is a plain related field to the company's contact; the branch does not copy it from Foods, so
    the plan sets it explicitly.
  - `stock.warehouse` uses the rule `company_id in company_ids`, so the branch warehouse is invisible to users
    working in Foods only, and the reverse.
- Pre-state: a new company gets no warehouse and a new branch gets no journals.
- Alternatives: a separate warehouse in Foods only (no branch) would split stock but not documents or users;
  analytic accounts would tag figures but not restrict staff.
- Who invoices for the branch (changed after the first test run, agreed with the user): branch staff keep only the
  Riverside branch in `res.users.company_ids` and work there (quotations, orders, stock). Branch invoices are issued
  by an accountant whose companies include Foods and Riverside, working with Riverside active: the invoice is still
  the branch's (`company_id` Riverside, RVINV journal). On a real database this is a user assignment (Foods'
  accountant gets `account.group_account_invoice` or `account.group_account_user` and both companies); the test
  stands in for it with the controller identity, which already has both companies and Bookkeeper rights.
- Odoo 20 finding (first run, measured): a user whose only company is the branch gets `AccessError` "Access to
  unauthorized or invalid companies." when creating a customer invoice with any taxed line. The same invoice
  without taxes, a sales order with taxed lines, and the same invoice by a user who also has Foods all succeed.
  Probable cause (deduced from the source, not confirmed as the executed path):
  `enterprise/account_reports/models/account_return.py`, `_compute_closing_account` and
  `_compute_sql_closing_account` switch to `self.env.company.root_id` with `with_company` without `sudo()`, and the
  root (Foods) is not among the user's companies.
- Pitfalls: the RVINV journal's priority depends on `sequence` being lower than Foods' sales journal (default 10 in
  the chart; measured 5 for Foods' INV after the apply, RVINV is 1). The identification by journal and company is for Odoo users; what the printed
  invoice shows is set in the document layout (see "Not covered").
- Sources: `knowledge/20.0/multi_company/companies_and_branches.md`, `knowledge/20.0/accounting/journals.md`,
  `knowledge/20.0/multi_company/shared_vs_company_records.md`

## Decision 4: Shared products and customers, per-company prices and taxes
- Ops: [op_110_product_haul] [op_120_product_management_fee] [op_130_product_frozen_case] [op_140_pricelist_foods] [op_150_pricelist_foods_item] [op_160_customer_harborview]
- Decision: products and the customer "Harborview Grocers" have `company_id` empty. Prices per company go through
  pricelists owned by a company: "Ridgeline Foods Wholesale" (`product.pricelist.company_id` = Foods) with a fixed
  price of 26.50 for the sample case (list price 30.00). It is set as the customer's
  `res.partner.property_product_pricelist` in Foods' context.
- Business reason: need 2. A single shared record per product and customer means nobody re-creates them, and
  company-dependent fields and company-owned pricelists keep prices per company.
- What Odoo does:
  - `res.partner` and `product.template` rules: `company_id = False` or `company_id parent_of company_ids`.
  - a shared product gets every company's default sales and purchase tax (`_force_default_tax`); each document only
    uses the taxes of its own company, so taxes stay per company without extra setup.
  - the haul and the fee are `type` `service`, `invoice_policy` `order`, so they can be invoiced on confirmation.
- Pre-state: pricelists are already enabled (`product.group_product_pricelist` implied by `base.group_user`), so
  the plan has no settings op for them.
- Alternatives: one copy of the customer per company (duplicates, which the requirement rules out); prices via a
  company-dependent cost field (only exists for cost, not for sale price).
- Pitfalls: sharing does not stop someone from typing a duplicate customer; Odoo shows a "similar VAT" hint only when
  the VAT matches. Restricting a shared product to one company later fails once another company sold it.
- Sources: `knowledge/20.0/multi_company/shared_vs_company_records.md`, `knowledge/20.0/sales_crm/pricelists.md`,
  `knowledge/20.0/sales_crm/invoicing_policy.md`

## Decision 5: Shared vendor, payment terms per company
- Ops: [op_170_vendor_summit_foods_terms] [op_180_vendor_summit_logistics_terms]
- Decision: one shared vendor "Summit Packaging Supply". Its `res.partner.property_supplier_payment_term_id` is
  "30 Days" in Foods and "45 Days" in Logistics, each written with the op's `company`.
- Business reason: need 2, "each company negotiates its own payment terms".
- What Odoo does: `property_supplier_payment_term_id` is company-dependent (one value per company on the same
  record); purchase orders and bills of each company pick up that company's value.
- Pre-state: the payment terms `account.account_payment_term_30days` and `account.account_payment_term_45days`
  exist and are shared (`company_id` empty).
- Alternatives: company-specific payment terms (`account.payment.term.company_id`) when a company needs its own
  term definitions, not just a different choice.
- Pitfalls: writing the field without the company context writes it for the bot's default company only. The second
  op adopts the same partner under a second key; that is intended.
- Sources: `knowledge/20.0/multi_company/shared_vs_company_records.md`, `knowledge/20.0/accounting/payment_terms.md`

## Decision 6: Per-company staff isolation
- Ops: [op_500_role_foods_staff] [op_510_role_branch_staff]
- Decision: no configuration is needed beyond giving each person only their company in `res.users.company_ids`.
  The two ops create test identities that prove it (see "Test identities").
- Business reason: need 3, first two sentences.
- What Odoo does: the global rules `company_id in company_ids` on `sale.order`, `purchase.order`, `account.move`,
  `account.payment`, `stock.warehouse` and `stock.picking.type`, and `parent_of` on `account.journal` (bank
  journals), hide other companies' documents. A user who cannot read a record cannot write it either.
- Pre-state: the rules ship with Odoo.
- Alternatives: none needed; the company is the isolation boundary.
- Pitfalls: a user with more than one company sees the union once both are selected in the switcher. Branch users
  see Foods' contacts, products, taxes and journals but not Foods' documents (by design).
- Sources: `knowledge/20.0/multi_company/user_company_access.md`, `knowledge/20.0/multi_company/shared_vs_company_records.md`

## Decision 7: Inter-company rules for hauls and management fees
- Ops: [op_200_intercompany_logistics] [op_210_intercompany_foods] [op_090_warehouse_logistics]
- Decision: on Logistics (receiving side), turn on `intercompany_generate_sales_orders` and
  `intercompany_generate_bills_refund`. On Foods, turn on `intercompany_generate_bills_refund`. Both use
  `intercompany_document_state` = `draft`. Logistics gets a warehouse "Logistics Yard" (RLY).
- Business reason: need 4 (Foods' haul purchase order becomes Logistics' sales order; Logistics' invoice becomes
  Foods' draft bill) and need 5 (Holdings' fee invoice becomes a draft bill in Foods and in Logistics).
- What Odoo does:
  - the rule sits on the receiving company, which is recognised from the document's partner (the company's
    `partner_id`). The generated document is created as the superuser and has `auto_generated` = true.
  - a sales order generated from a purchase order has `auto_purchase_order_id` = the PO. A vendor bill generated from
    an invoice has `auto_invoice_id` = the invoice and lands in the receiving company's first purchase journal
    (`intercompany_purchase_journal_id`).
  - the generated sales order needs a warehouse in Logistics, otherwise `UserError` "Configure correct warehouse for
    company(...)".
- Pre-state: the settings do not exist before op_010.
- Alternatives: manual mirror documents when volume is low.
- Pitfalls: Holdings has no inter-company setting because it only issues documents. The rule does not fire on
  documents it generated itself, so there are no loops.
- Sources: `knowledge/20.0/multi_company/intercompany_rules.md`, `knowledge/20.0/multi_company/per_company_settings.md`

## Decision 8: Group controller: Bookkeeper everywhere, no entries in Logistics
- Ops: [op_300_group_controller_marker] [op_310_controller_restrict_moves] [op_320_controller_restrict_move_lines] [op_520_role_group_controller]
- Decision: the controller gets `account.group_account_user` (Bookkeeper) and every Ridgeline company in
  `company_ids`. A marker group "Ridgeline group controller" (`res.groups`) identifies them. Two global restrictions
  (`ir.access` with no `group_id`, `operation` `cud`) on `account.move` and `account.move.line` evaluate:
  `[('company_id.name', 'in', [Holdings, Foods, Riverside Branch, Eliminations])] if user.has_group(<marker>) else []`.
- Business reason: need 3, last sentence, and need 6 (the controller posts the elimination entries in Ridgeline
  Eliminations). Agreed with the user: Bookkeeper plus an allow-list restriction that fails closed.
- What Odoo does:
  - in 20.0 an `ir.access` without `group_id` has `kind` `restriction` and is AND-ed with every group permission.
    `operation` `cud` leaves reading untouched, so the controller still sees Logistics and runs reports on it.
  - the domain is evaluated with `user` in its context (`ir.access._eval_context`: `user`, `time`, `company_ids`,
    `company_id`), so the conditional applies to marker-group members only. Every other user gets `[]` (no
    restriction).
  - restricting journal items too blocks payments, statement lines and reconciliations in Logistics, which all
    create or write `account.move.line` as the user. Inter-company documents are generated as the superuser and are
    not affected.
  - Bookkeeper, not Administrator: `account.group_account_manager` could change Logistics' journals, accounts, taxes
    and lock dates, which the restriction does not cover. Bookkeeper has read-only access to those.
  - the controller's error is an `AccessError` "Sorry, ... doesn't have 'create' access to: - Journal Entry
    (account.move)" (`ir.access._make_record_access_error`).
- Pre-state: no such group or restriction exists.
- Alternatives: read-only controller (`account.group_account_readonly`; rejected, because the controller must post
  eliminations); full accountant without restriction (does not meet the requirement).
- Pitfalls:
  - the domain names companies by `name`, because its eval context has no `ref()` and a plan reference cannot go
    inside a string. Renaming an allowed company or adding a new one blocks the controller there until the list is
    updated (fails closed, as agreed).
  - the marker is referenced by its external id `__ofa__.grp_group_controller`, which exists because `ofa` created
    the group. On a real database the group needs its own module xmlid and the domain must name it.
  - the restriction runs on every `account.move` write for every user (an empty domain for most); the cost is one
    group lookup per check.
- Sources: `knowledge/20.0/multi_company/shared_vs_company_records.md` (record rules are `ir.access`),
  `knowledge/20.0/multi_company/user_company_access.md`, `knowledge/20.0/accounting/invoicing_vs_accounting_apps.md`;
  the eval context and the error text were read in the 20.0 source (`odoo/addons/base/models/ir_access.py`), not in
  a compendium entry.

## Decision 9: Group reporting
- Ops: none beyond [op_050_company_eliminations] and [op_010_install_modules].
- Decision: per-company and group P&L and balance sheet are the US reports (`l10n_us_reports.profit_and_loss`,
  `l10n_us_reports.balance_sheet`) run with one company or with every Ridgeline company selected in the company
  switcher. Inter-company figures are found with the Interco Comparison report
  (`account_reports.interco_comparison_report`). Each month the controller posts an elimination entry in Ridgeline
  Eliminations that reverses the inter-company revenue (hauls, fees) against the matching expense.
- Business reason: need 6.
- What Odoo does:
  - `account.report.filter_multi_company` = `selector` adds up the selected companies. There is no consolidation
    module in 20.0, so nothing eliminates automatically.
  - `account.report.get_options(previous_options)` builds the report options. `previous_options['forced_companies']`
    (a list of company ids) overrides the switcher selection (`_init_options_companies`), so a test can run the same
    report over Holdings+Foods+branch+Logistics and again with Eliminations added. `date` (custom range) and
    `hide_0_lines` = false fix the period and keep every line in place.
  - `get_report_information(options)` returns `lines`. Each line has `name` and `columns` with the raw amount in
    `no_format`. The US P&L (`l10n_us_reports.profit_and_loss`) has nine report lines, none `hide_if_zero`
    (`account.report.line` by `sequence`). **Corrected after the run:** the plan first assumed the output had those
    nine lines only; measured on t27_2, `get_report_information` returns 11, because Revenue and Cost of Sales are
    each followed by a total line: Revenue, Total Revenue, Cost of Sales, Total Cost of Sales, Gross Profit,
    Expense, Net Operating Income, Other Income, Other Expense, Net Other Income, Net Income. The test reads
    `lines.0`, `lines.2` and `lines.10`. Lines grouped by account stay folded unless `unfold_all` is set.
  - in the US chart the company's default income account is "Product Sales" (`account_type` income → Revenue line)
    and its default expense account is "Cost of Goods Sold" (`expense_direct_cost` → Cost of Sales line); read on
    `res.company.income_account_id` / `expense_account_id` of a US demo company. Inter-company invoices hit Product
    Sales on the seller and Cost of Goods Sold on the buyer's generated bill. So the monthly elimination entry in
    Ridgeline Eliminations debits its own Product Sales and credits its own Cost of Goods Sold by the inter-company
    total.
- Pre-state: both US reports already have `filter_multi_company` = `selector` (`ofa inspect` on `account.report`),
  so no op is needed.
- Alternatives: eliminate in a spreadsheet outside Odoo (rejected by the user); dedicated inter-company income and
  expense accounts per company, which make the elimination amount readable straight from the trial balance (worth
  adding if non-group sales ever share Product Sales in volume; not needed to prove the mechanism).
- Pitfalls:
  - the group figure is only correct when Eliminations is selected together with the others, and only once that
    month's elimination entry is posted. The per-company reports must not include Eliminations.
  - the entry eliminates revenue and cost; inter-company receivables and payables still show in the group balance
    sheet until they are paid. Eliminating them is the same mechanism (debit payable, credit receivable in
    Eliminations) and is not part of the test.
  - the test asserts by line position (`lines.0`, `lines.2`, `lines.10`), anchored by also checking each line's
    `name`. A change of the US report layout would show up as a name mismatch, not as a silent wrong number.
- Sources: `knowledge/20.0/multi_company/multi_company_reporting.md`; the options and lines format were read in the
  20.0 source (`enterprise/account_reports/models/account_report.py`: `_init_options_companies`,
  `_init_options_hide_0_lines`, `get_report_information`), not in a compendium entry.

## Decision 10: Monthly management fee by recurring invoice (auto-post)
- Ops: none. `auto_post` is a field of each invoice, set by Holdings' accountant on the first fee invoice per
  operating company, not company configuration.
- Decision: Holdings' first fee invoice to each operating company is saved with `account.move.auto_post` =
  `monthly` (Auto-post: Monthly). Each month Odoo creates and posts the next one, and the inter-company rule turns
  each posted invoice into the receiver's draft bill.
- Business reason: need 5, "every month".
- What Odoo does (`odoo/addons/account/models/account_move.py@20.0`):
  - `_post` calls `_copy_recurring_entries` for moves with `auto_post` in monthly/quarterly/yearly. That creates a
    draft copy dated one month later (`_apply_delta_recurring_entries`, which keeps the day of the month of the
    origin), with the same `auto_post`, `auto_post_until`, `auto_post_origin_id` = the first invoice, and
    `invoice_date` moved by the same delta. It does not create a second copy for a date that already has one.
  - the daily cron `account.ir_cron_auto_post_draft_entry` (`_autopost_draft_entries`, active in the template) posts
    drafts with `auto_post` != `no` and `date` <= today. That post creates the following month's copy.
  - `account_inter_company_rules` overrides `_post`, so every posted copy generates the receiver's bill, created as
    the superuser, in draft (`intercompany_document_state`).
  - a recurring move cannot be posted by hand before its date: `UserError` "This move is configured to be
    auto-posted on ...".
  - `auto_post_until` (optional) ends the series; empty means no end.
- Pre-state: the cron is active (`ofa inspect` on `ir.cron`). No op is needed.
- Alternatives: Subscriptions (`sale_subscription`) when the fee needs contract management (price changes, renewals,
  customer portal). For a fixed internal fee, auto-post is enough and needs no other app.
- Pitfalls:
  - changing the fee means editing the next draft copy (the copy carries the amount forward).
  - if a post fails (for example a lock date), the cron sets that draft's `auto_post` to `no` and logs the reason on
    it, and the series stops until someone fixes it.
  - the test cannot wait for the cron. It posts the next month's copy by hand on a past date, which runs the same
    `_post` (with `soft` false instead of the cron's `soft` true; the only difference is the future-date handling,
    which does not apply to a past date).
- Sources: uncited, no compendium entry. Read in the 20.0 source (`account_move.py`: `auto_post`,
  `_copy_recurring_entries`, `_get_fields_to_copy_recurring_entries`, `_autopost_draft_entries`;
  `enterprise/account_inter_company_rules/models/account_move.py`: `_post`). Names checked with
  `ofa inspect --target t27 account.move --fields auto_post,...` and `ofa inspect --target t27 ir.cron`.

## Test identities
| Role | Test user | Groups and companies | Op |
|---|---|---|---|
| Foods staff | ofa_user_1 | `base.group_user`, `sales_team.group_sale_salesman_all_leads`, `purchase.group_purchase_user`, `stock.group_stock_user`, `account.group_account_invoice`; Foods only | [op_500_role_foods_staff] |
| Riverside branch staff | ofa_user_2 | same groups; Riverside branch only | [op_510_role_branch_staff] |
| Group controller | ofa_user_3 | `base.group_user`, `account.group_account_user`, the marker group, `base.group_multi_company`; all five Ridgeline companies, default Holdings | [op_520_role_group_controller] |

The accountant who issues branch invoices (Foods + Riverside) has no test user of its own; the group controller
identity (ofa_user_3) stands in for it in t27_branch, because it is a non-administrator Bookkeeper with Foods and
Riverside in its companies and Riverside on its posting allow-list.
Logistics staff and the Logistics accountant have no test user (only three exist). Isolation is symmetric, so the
Foods staff checks cover it. The Logistics accountant is stood in for by `ofa_bot`, which lacks the marker group.

## Test plan
Scenarios to write after the apply. Every need of the requirement gets a row.

| Need (from requirement.md) | Scenario | What it checks |
|---|---|---|
| 1. Three legal companies with own chart, journals, bank, numbering | t27_structure | each of Holdings, Foods, Logistics, Eliminations: `parent_id` false, `chart_template` = `us`; each root has ≥1 `sale` and ≥1 `bank` `account.journal` of its own; Holdings/Foods/Logistics `vat` as planned |
| 1. Branch shares Foods' tax ID, invoices identifiable, own stock | t27_branch | branch `parent_id` = Foods, `vat` = 00-0000102, no own `bank` journal. As branch staff (company branch): a sales order is created in the branch (`company_id` branch, `warehouse_id` RFR); creating a taxed customer invoice is refused (`AccessError`, "Access to unauthorized or invalid companies.", the Odoo 20 finding) and no invoice with its `ref` exists. As the accountant stand-in (controller, company branch): a taxed customer invoice posts with `company_id` = branch, `journal_id` = RVINV journal, `name` contains "RVINV", `amount_tax` > 0. As Foods staff: an invoice gets Foods' INV journal. Branch staff finds the RFR warehouse and not RFM; Foods staff finds RFM and not RFR |
| 2. Shared products and customers | t27_shared_data | the customer and the three products have `company_id` false; Foods staff, branch staff and a Logistics-context search each find them (count 1) |
| 2. Vendor terms per company | t27_shared_data | `property_supplier_payment_term_id` of the vendor read in Foods = 30 Days, in Logistics = 45 Days |
| 2. Prices and taxes per company | t27_shared_data | as Foods staff, a sales order to the customer gets `pricelist_id` = Foods Wholesale, line `price_unit` 26.5, and no line tax from another company (search on `tax_ids.company_id` != Foods: count 0). In Logistics, the same product's line has `price_unit` 30.0 and only Logistics taxes |
| 3. Staff only in their company | t27_isolation | records created by the bot in Logistics (a sales order, a draft invoice) and in the branch (a sales order): as Foods staff, searches for them, for Logistics' bank journal and for the RLY warehouse return 0; a write as Foods staff on the Logistics invoice is refused (`AccessError`, "doesn't have 'write' access to") and its `ref` is unchanged |
| 3. Branch staff only in the branch | t27_isolation | as branch staff, a Foods sales order created by the bot is not found (count 0) |
| 3. Controller sees every company and switches | t27_controller | as controller without a company key (all companies active): finds the Logistics and Foods invoices (count 2); with `company` = Logistics, finds the Logistics invoice |
| 3. Controller does not post in Logistics | t27_controller | as controller: a misc entry in Eliminations is created and posted (`state` = posted); one in Foods too. Creating an entry in Logistics is refused (`AccessError`, "doesn't have 'create' access to"), and no entry with that `ref` exists afterwards. Posting the existing Logistics draft invoice is refused (`AccessError`, "doesn't have 'write' access to") and its `state` stays draft. The bot (no marker group) can create a Logistics entry, so the restriction is scoped to the marker |
| 3. Controller runs reports for several companies | t27_group_reporting | as controller with no company key (all five companies active): `get_options` of the US P&L and balance sheet saved with `save_as`; `check` on `companies` has count 5. `get_report_information` returns lines (count ≥ 1) |
| 4. Foods PO to Logistics → Logistics SO | t27_haul_flow | Foods PO to Logistics' partner with the haul (1 × 850) confirmed; `sale.order` with `auto_purchase_order_id` = PO: count 1, `company_id` = Logistics, `partner_id` = Foods' partner, `state` draft, `auto_generated` true, `amount_untaxed` 850 |
| 4. Logistics invoice → Foods draft bill | t27_haul_flow | the SO is confirmed and invoiced (advance-payment wizard), invoice posted in Logistics; `account.move` with `auto_invoice_id` = invoice: count 1, `company_id` = Foods, `move_type` in_invoice, `state` draft, `amount_untaxed` 850 |
| 5. Holdings fee invoices → draft bills | t27_management_fee | Holdings posts a fee invoice to Foods (12000) and one to Logistics (9000), both `auto_post` = monthly with `invoice_date` 2026-06-01; each has a generated bill (`auto_invoice_id` = invoice): `company_id` = Foods / Logistics, `move_type` in_invoice, `state` draft, `amount_untaxed` 12000 / 9000 |
| 5. "Every month" (recurrence) | t27_management_fee | after posting, one draft copy per invoice exists (`auto_post_origin_id` = invoice): `state` draft, `auto_post` monthly, `invoice_date` 2026-07-01, `company_id` Holdings, `amount_untaxed` 12000 / 9000. Posting the July copy of the Foods fee (stand-in for the cron, see Decision 10) gives a new draft bill in Foods (`auto_invoice_id` = the copy, 12000) and an August copy (`invoice_date` 2026-08-01, draft) |
| 5. Cron posts on the date | **Not tested** | the cron runs on its own schedule; the test cannot advance the clock. It is proven only by the code path shared with the manual post above |
| 6. P&L and balance sheet per company and for the group | t27_group_reporting | September 2026 documents only (no other scenario posts in September): Logistics invoices Foods 850 (haul), Holdings invoices Foods 12000 and Logistics 9000; the three generated bills get `invoice_date` 2026-09-15 and are posted by the bot. As controller, US P&L `get_options` with `forced_companies` = [Holdings], date 2026-09-01..30, `hide_0_lines` false, then `get_report_information`: `lines.0.name` = "Revenue", `lines.0.columns.0.no_format` = 21000. Balance sheet over the four group companies: `get_report_information` returns lines (count ≥ 1) |
| 6. No double counting of inter-company sales | t27_group_reporting | same period, `forced_companies` = Holdings, Foods, branch, Logistics (no Eliminations): Revenue = 21850, Cost of Sales (`lines.1`) = 21850, Net Income (`lines.8`) = 0 (both sides counted). The controller then posts the September elimination entry in Ridgeline Eliminations (debit its Product Sales 21850, credit its Cost of Goods Sold 21850, `date` 2026-09-30, `state` posted). With Eliminations added to `forced_companies`: Revenue = 0, Cost of Sales = 0, Net Income = 0. Each amount check also checks the line `name`. If the format does not allow the assertion, the report says so with the exact error |

## Not covered by this plan
- **Starting the fee series**: Holdings' accountant creates the first fee invoice per operating company with
  Auto-post = Monthly (Other Info tab of the invoice). That is a document, not configuration, so the plan has no op
  for it (Decision 10).
- **Elimination entries**: posted by hand each month by the controller in Ridgeline Eliminations, from the Interco
  Comparison report. Odoo 20.0 has no automatic elimination. Inter-company receivables and payables are not
  eliminated by the P&L entry (Decision 9).
- **Bank accounts**: each root company gets a Bank journal from its chart. Real account numbers are added in
  Accounting > Configuration > Journals per company and are out of scope for a demo.
- **Printed branch identification**: the invoice header shows the issuing company's address and layout from
  Settings > Companies > Document Layout, configured in the UI per company.
- **The admin user** does not get the new companies (only `ofa_bot` does). Add them in Settings > Users if the UI
  should show them to the admin.
- **Real database**: the controller restriction's domain names the marker group by its `__ofa__` external id; a real
  rollout gives the group a module external id and updates the domain.
- **Branch staff issuing taxed invoices themselves**: blocked by the Odoo 20 behaviour in Decision 3. Letting them
  do it either gives them Foods as a company (they could then switch to Foods and see its documents) or needs a code
  fix in `account_reports` (development, outside configuration).
- **Duplicate prevention**: sharing makes the customer visible to everyone; it does not block a typed duplicate.

## Glossary
- **Root company / branch**: a legal entity (`res.company` without `parent_id`) vs an operating unit of one
  (`res.company` with `parent_id`) that shares its books.
- **Company-dependent field**: one value per company on a shared record (`property_supplier_payment_term_id`,
  `property_product_pricelist`).
- **Inter-company rule**: a per-company setting that makes Odoo create the mirror document in the receiving company.
- **Restriction (`ir.access` without group)**: a record rule AND-ed with every permission; here, a domain that only
  narrows the controller.
- **Elimination entry**: a journal entry that cancels inter-company revenue against the matching expense so group
  totals do not count them twice.
