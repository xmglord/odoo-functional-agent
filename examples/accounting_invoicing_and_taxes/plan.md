# Lumen Ridge Studios: invoicing, payments and monthly close

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise
- Areas: accounting, sales_crm

## Summary
Lumen Ridge Studios moves invoicing, bank matching and the month-end close from a spreadsheet into Odoo. Demo
company 1 ("My Company (San Francisco)", USD, generic chart with a 15% sales tax) stands in for the studio. The plan
installs the full Accounting app, reuses the chart's auto-applied "Foreign Trade" position for customers abroad
(adding the export-of-services mention), adds a retainer payment term with a 2% early payment discount that reduces
tax, a euro bank journal and pricelist, mandatory project and department analytics on invoices and bills, and two
roles: a billing clerk who cannot touch journal entries, taxes or lock dates, and an accountant who closes the month.

## Decision 1: Full Accounting app
- Ops: [op_010_install_accountant]
- Decision: install the Enterprise app `accountant` ("Accounting").
- Business reason: the requirement needs bank reconciliation by the accountant (need 4), month close with lock
  dates (need 6) and analytic reporting (need 5). On the template only `account` and `account_accountant`
  (Enterprise "Invoicing") are installed.
- What Odoo does:
  - `accountant` makes `account.group_account_manager` imply `account.group_account_user` ("Bookkeeper") and
    gives the admin (so `ofa_bot`) Bookkeeper rights, needed to read `account.analytic.plan` and
    `account.analytic.applicability` (the bot got `AccessError` on the latter before the install).
  - Paid invoices go to `in_payment` until the bank line is matched. The scenarios pay through bank statement
    lines (`account.bank.statement.line.set_line_bank_statement_line`), which is how the accountant works, so
    invoices end `paid`.
- Pre-state: `accountant` is `uninstalled` on t25 (checked with `ofa inspect ir.module.module`).
- Alternatives: Invoicing only (`account_accountant`): no Bookkeeper group, and the accountant would rebuild the
  close outside Odoo, which is what the business wants to stop.
- Pitfalls: its post-init starts the accounting onboarding; harmless on a demo DB.
- Sources: `knowledge/20.0/accounting/invoicing_vs_accounting_apps.md`

## Decision 2: Taxes from the customer, export of services at 0% with its reason
- Ops: [op_050_export_fpos] [op_060_export_tax_label] [op_070_product_project] [op_080_product_retainer] [op_090_product_subcontract] [op_100_product_software]
- Decision: products carry the domestic 15% tax (`account.1_sale_tax_template` / `account.1_purchase_tax_template`);
  the fiscal position picks the tax from the customer's country. The chart's "Foreign Trade" position
  (`account.1_template_generic_export_fiscal_position`, `auto_apply`, no country, sequence 20) already applies to
  every customer outside the US and maps 15% to "0% Exports" (`account.1_sale_export_tax_template`). The plan adds
  the legal mention on the position (`account.fiscal.position.note`: "Export of services: not subject to sales
  tax.") and the line label `account.tax.invoice_label` "0% (export of services)", and restates the 20.0 tax-side
  mapping (`account.tax.fiscal_position_ids`, `account.tax.original_tax_ids`) so the plan owns it.
- Business reason: need 1. Nobody chooses a tax on a line: `account.move.fiscal_position_id` is computed from the
  customer and `account.move.line.tax_ids` is the mapped product tax.
- What Odoo does: "Domestic" (`account.1_template_generic_domestic_fiscal_position`, country US, sequence 10)
  matches US customers first; Foreign Trade catches the rest. The note prints on the invoice.
- Pre-state: the mapping and auto-apply already hold in the template, so [op_050_export_fpos] and
  [op_060_export_tax_label] are `adopted` only for the note and label; the 15% default sales tax
  (`res.company.account_sale_tax_id`) already holds and has no op.
- Alternatives: set `property_account_position_id` on each foreign customer (explicit, but someone must remember
  it); a separate position per country group (EU vs rest of world) if the legal mention differs.
- Pitfalls: Foreign Trade also maps purchase 15% to "0% Imports" for foreign vendors (chart default, kept). A
  customer without a country gets no auto position, so it is taxed as the product says (15%).
- Sources: `knowledge/20.0/accounting/fiscal_positions.md`, `knowledge/20.0/accounting/taxes_and_tax_groups.md`

## Decision 3: Payment terms (projects 30/70, retainers 15 days with 2% early discount)
- Ops: [op_110_term_retainer] [op_120_term_retainer_line] [op_230_cust_cedar] [op_240_cust_harbor] [op_250_cust_nordlicht] [op_260_vend_pixel] [op_270_vend_clouddesk]
- Decision:
  - Projects: one sales order per project. At signature the clerk invoices a 30% down payment
    (`sale.advance.payment.inv`, `advance_payment_method = 'percentage'`, `amount = 30`); at delivery the regular
    invoice (`advance_payment_method = 'delivered'`) bills 100% and deducts the down payment, leaving 70%. Project
    customers default to `account.account_payment_term_30days` (`res.partner.property_payment_term_id`), so the
    delivery invoice is due in 30 days.
  - Retainers: new term "Retainer: 15 days, 2% within 10 days" (`account.payment.term`: `early_discount = true`,
    `discount_percentage = 2`, `discount_days = 10`, `early_pay_discount_computation = 'included'`), one 100% line
    at 15 days (`account.payment.term.line`: `delay_type = 'days_after'`, `nb_days = 15`). Retainer customers get
    it as their default term.
  - Vendors: the subcontractor Pixel Forge Contractors and the software vendor CloudDesk Software (both US), used
    for the bills of need 5; they keep the template's vendor term (none).
- Business reason: need 2. 'included' ("On early payment") books the 2% discount at payment time and splits it
  between income and tax, so the tax is reduced in proportion, not only the total.
- What Odoo does: the term creates the receivable line's `date_maturity`; when a bank line for the discounted
  amount arrives within 10 days, matching proposes the discount and books it to the company's
  `account_journal_early_pay_discount_loss_account_id` ("Cash Discount Loss") plus a tax line that reverses 2% of
  the tax.
- Pre-state: the 30-day term exists in the template; the retainer term does not. The term's default line (100%,
  0 days) is adopted by [op_120_term_retainer_line] and moved to 15 days.
- Alternatives: one invoice with a 30%/70% installment term (wrong here: the 70% is billed later, on delivery);
  `early_pay_discount_computation = 'mixed'` reduces the tax on the invoice itself (Belgian style), even when the
  customer pays late.
- Pitfalls: early discount only works on a single 100% line. The down payment invoice inherits the order's term
  (30 days); if the business wants it payable at once, the clerk sets "Immediate Payment" on that draft. The term
  on the partner only fills new documents.
- Sources: `knowledge/20.0/accounting/payment_terms.md`; down payment wizard names: uncited, checked in
  `odoo/addons/sale/wizard/sale_make_invoice_advance.py@20.0` (fields `advance_payment_method`, `amount`,
  `sale_order_ids`, method `create_invoices`).

## Decision 4: Euros: currency, pricelist and exchange differences
- Ops: [op_020_settings] [op_030_currency_eur] [op_220_pricelist_eur] [op_250_cust_nordlicht]
- Decision: activate EUR (`res.currency.active`), turn on pricelists (`group_product_pricelist`) and give European
  customers the "Europe (EUR)" pricelist (`res.partner.property_product_pricelist`). Their sales orders are in EUR,
  so the invoices from them are in EUR (`account.move.currency_id`).
- Business reason: need 3. Exchange differences are booked automatically at reconciliation to the company's
  `currency_exchange_journal_id` ("Exchange Difference"), `income_currency_exchange_account_id` ("Foreign
  Exchange Gain") and `expense_currency_exchange_account_id` ("Foreign Exchange Loss"), as
  `account.partial.reconcile.exchange_move_id`, so no balance stays open on the customer.
- Pre-state: the three exchange-difference fields are already set on company 1 (checked with `ofa inspect
  res.company`), so no op; EUR is inactive.
- Alternatives: a sale journal with `currency_id` EUR for invoices typed directly (not from an order): the journal
  then forces EUR. Not needed while all customer invoicing goes through sales orders.
- Pitfalls: Odoo has no "invoice currency" on the customer. An invoice the clerk types by hand (not from an order)
  starts in USD and the clerk must pick EUR. Rates must exist: `currency_rate_live` is installed but its cron does
  not run on demo targets; scenarios create `res.currency.rate` records themselves.
- Sources: `knowledge/20.0/accounting/multi_currency.md`

## Decision 5: Two bank accounts; matching bank lines with several invoices, partial payments and refunds
- Ops: [op_040_bank_eur]
- Decision: the template's bank journal "Bank" (`account.1_bank`, code BNK1, USD) is the operating account; a new
  journal "Bank EUR" (`account.journal`, `type = 'bank'`, `code = 'BNKEU'`, `currency_id` EUR) is the euro account.
  The accountant matches each bank statement line (`account.bank.statement.line`) with one or more open invoice
  lines (`set_line_bank_statement_line`); an amount smaller than the invoices leaves `payment_state = 'partial'`
  with the exact `amount_residual`. A partial refund is a credit note from the reversal wizard
  (`account.move.reversal.refund_moves`), so `account.move.reversed_entry_id` ties it to the original invoice.
- Business reason: need 4.
- Pre-state: BNK1 exists; BNKEU does not. Payment method lines have no outstanding account
  (`payment_account_id`); left as is, because payments are recorded by matching bank lines, not by the
  register-payment wizard.
- Alternatives: register payments with the wizard and an outstanding account, then match the statement later
  (two steps); reconciliation models (`account.reconcile.model`) to automate matching of recurring payers.
- Pitfalls: the clerk does not register payments in this design (and the restriction of Decision 7 would stop a
  clerk payment, because a payment's journal entry is `move_type = 'entry'`).
- Sources: `knowledge/20.0/accounting/journals.md`, `knowledge/20.0/accounting/payments_and_reconciliation.md`;
  `set_line_bank_statement_line` uncited, checked in
  `enterprise/account_accountant/models/account_bank_statement.py@20.0`.

## Decision 6: Projects and departments as mandatory analytics
- Ops: [op_130_dept_design] [op_140_dept_engineering] [op_150_proj_brand] [op_160_proj_portal] [op_170_proj_retainer] [op_180_mandatory_projects_invoice] [op_190_mandatory_projects_bill] [op_200_mandatory_departments_invoice] [op_210_mandatory_departments_bill]
- Decision: reuse the template plans "Project Plan" (`analytic.analytic_plan_projects`) and "Departments"
  (`analytic.analytic_plan_departments`); add the departments Design and Engineering and three projects
  (LR-001 Brand Refresh, LR-002 Client Portal, LR-003 Cedar Lane Retainer) as `account.analytic.account`. Both plans
  are `mandatory` for the business domains `invoice` and `bill` in company 1
  (`account.analytic.applicability`), so a line without 100% on a project and 100% on a department cannot be
  posted.
- Business reason: need 5. Posting creates `account.analytic.line` records per plan; the Analytic Report
  (Accounting > Reporting > Analytic Report) and `account.analytic.account.balance` give revenue minus costs per
  project and per department without a spreadsheet.
- Pre-state: the plans and other demo accounts exist; Design, Engineering and the projects do not; no
  applicability is mandatory.
- Alternatives: the Project app (`project`) creates one analytic account per project and adds task tracking; not
  chosen (clarification). Distribution models (`account.analytic.distribution.model`) can prefill a retainer
  customer's project.
- Pitfalls: distribution keys are account ids, so the clerk picks them on each order or invoice line; the down
  payment and final invoice lines inherit the order line's distribution. Mandatory only checks product lines.
- Sources: `knowledge/20.0/accounting/analytic_accounting.md`

## Decision 7: Roles: clerk vs accountant
- Ops: [op_280_no_manual_entries]
- Decision: the clerk has `account.group_account_invoice` ("Invoicing") and `sales_team.group_sale_salesman`;
  the accountant has `account.group_account_manager`. Standard rights already stop the clerk from changing taxes
  (`account.tax` is read-only below `account.group_account_manager`) and lock dates (the lock wizard
  `account.change.lock.date` and `account.lock_exception` are for `account.group_account_manager`; the company
  record is for administrators). They do **not** stop manual entries: the Invoicing group has full CRUD on
  `account.move` with no domain (`account_move_see_all` in `account/security/ir.access.csv`), only the menu is
  hidden. So the plan adds a global restriction (`ir.access` without group, operation `cud`) on
  `account.move`: users without `account.group_account_user` may only create, change or delete moves whose
  `move_type` is not `entry`.
- Business reason: need 6, first sentence.
- Pre-state: no such restriction exists.
- Alternatives: rely on the hidden menu (a clerk can still create entries by import or RPC); journal hashing
  (`restrict_mode_hash_table`) makes entries tamper-evident but does not stop them.
- Pitfalls: the restriction also stops clerks from registering payments and from any flow that writes a
  miscellaneous entry as the clerk (exchange differences, early-discount write-offs); those are the accountant's
  job here. A Bookkeeper (`account.group_account_user`) passes the restriction: "only the accountant" is enforced
  as "only accounting users". The domain is evaluated per user with `user.has_group` (uncited: no compendium entry;
  `ir.access` names checked in `odoo/odoo/addons/base/models/ir_access.py@20.0`).
- Sources: `knowledge/20.0/accounting/invoicing_vs_accounting_apps.md`, `knowledge/20.0/accounting/lock_dates.md`

## Decision 8: Monthly close with the Global Lock Date
- Ops: none (closing is a monthly action, not configuration). The scenarios close August as the accountant.
- Decision: the accountant closes a month with the lock wizard (`account.change.lock.date`,
  `fiscalyear_lock_date`, method `change_lock_date`), which writes `res.company.fiscalyear_lock_date`. It applies to
  everyone, the accountant included (`_get_user_lock_date` has no group bypass). Reopening on purpose is the same
  wizard with an earlier date: it creates an `account.lock_exception` (for the accountant or everyone, for a
  duration, with a reason), leaving an audit trail.
- Business reason: need 6, last two sentences. Not `hard_lock_date`: that one can never be moved back, and the
  business wants to be able to reopen.
- What Odoo does: changing or deleting a posted entry dated in the locked month raises "You cannot add/modify
  entries prior to and inclusive of: ..."; posting a new document dated in it does not fail but moves its
  accounting `date` after the lock (the `invoice_date` keeps the original date).
- Pre-state: no lock dates are set on company 1.
- Alternatives: `sale_lock_date` / `purchase_lock_date` to close only invoicing; `tax_lock_date` after filing.
- Pitfalls: locking fails while unreconciled bank statement lines exist on or before the date (the template's are
  in September and October, so August can be locked). The "postpone" behaviour means "cannot post in it" is met by
  moving the entry out of the closed month, not by an error.
- Sources: `knowledge/20.0/accounting/lock_dates.md`

## Test identities
| Role | Test user | Groups and companies | Op |
|---|---|---|---|
| Billing clerk | ofa_user_1 | `base.group_user`, `account.group_account_invoice`, `sales_team.group_sale_salesman`; company 1 | [op_500_role_clerk] |
| Accountant | ofa_user_2 | `base.group_user`, `account.group_account_manager`; company 1 | [op_510_role_accountant] |

## Test plan
Scenarios to write after the apply. Clerk steps act as ofa_user_1, accountant steps as ofa_user_2. Scenarios named
"neg" are negative tests: `ofa` has no "expect an error" step, so each one ends in the forbidden call and its
**expected result is fail** at that step with the named error; a pass would mean the control is missing.

| Need (from requirement.md) | Scenario | What it checks |
|---|---|---|
| 1. Domestic customers get the standard sales tax, automatically | lr_tax_domestic_vs_export | clerk invoice for Harbor Point (US): `fiscal_position_id` = Domestic, line `tax_ids` = [15%], `amount_tax` = 15% of the base |
| 1. Customers abroad: no tax, invoice says why | lr_tax_domestic_vs_export | clerk invoice for Nordlicht (DE): `fiscal_position_id` = Foreign Trade, line `tax_ids` = [0% Exports], `amount_tax` = 0; the position's `note` contains "Export of services" |
| 2. Projects 30% at signature, 70% on delivery due in 30 days | lr_project_down_payment | clerk sales order 10,000 for Harbor Point: down payment invoice `amount_untaxed` = 3,000; final invoice `amount_untaxed` = 7,000, `invoice_payment_term_id` = 30 Days, `invoice_date_due` = invoice date + 30 |
| 2. Retainers due in 15 days, 2% within 10 days, tax reduced in proportion | lr_retainer_early_discount | invoice 1,000 + 150 tax for Cedar Lane dated 2026-10-01: term = retainer, `invoice_date_due` = 2026-10-16; accountant matches a bank line of 1,127.00 on 2026-10-08: invoice `paid`, `amount_residual` = 0; the bank move has a 20.00 line on Cash Discount Loss and a 3.00 tax line on the 15% tax |
| 3. EUR invoice and payment, exchange difference booked automatically | lr_eur_exchange_difference | rates 0.90 (2026-09-01) and 0.85 (2026-09-20); clerk order for Nordlicht: invoice `currency_id` = EUR; accountant matches a 1,000 EUR line on Bank EUR: invoice `paid`, `amount_residual` = 0, receivable line `reconciled`, an `account.partial.reconcile` with `exchange_move_id` set |
| 4. Two bank accounts | lr_eur_exchange_difference, lr_bank_multi_invoice_partial | EUR line on BNKEU, USD lines on BNK1 |
| 4. One transfer pays several invoices; partial payment shows exact amount owed | lr_bank_multi_invoice_partial | two invoices of 1,150 for Harbor Point, one bank line of 2,000 matched with both: one `paid` with residual 0, the other `partial` with `amount_residual` = 300 |
| 4. Partial refund is a credit note tied to the invoice | lr_partial_refund_credit_note | paid invoice of 1,150; clerk credit note from the reversal wizard for 200 + 30 tax: `move_type` = `out_refund`, `reversed_entry_id` = the invoice, `amount_total` = 230; accountant matches an outgoing bank line of -230: credit note `paid` |
| 5. Every invoice and bill assigned to project and department | lr_neg_unassigned_analytic | **expected fail**: clerk posts an invoice line with no distribution, refused with "One or more lines require a 100% analytic distribution" |
| 5. Revenue, costs and margin by project and by department | lr_profitability | clerk invoice for Client Portal (3,000 Design + 2,000 Engineering) and bills 1,200 (Engineering, subcontractor) and 300 (Design, software): Client Portal `balance` = 3,500; analytic lines of these moves: Design +3,000 / -300, Engineering +2,000 / -1,200. Screenshot of the Analytic Report is best-effort |
| 6. Clerk creates and sends invoices, records bills | lr_tax_domestic_vs_export, lr_profitability | the clerk's invoices and bills reach `state` = `posted`. "Sends" (email) is **Not tested**: no outgoing mail server on demo targets |
| 6. Clerk cannot post manual journal entries | lr_neg_clerk_manual_entry | **expected fail**: clerk creates an `entry` move in MISC, refused by the access restriction |
| 6. Only the accountant posts adjustments | lr_accountant_adjustment | accountant creates and posts a manual entry in MISC: `state` = `posted` |
| 6. Clerk cannot change taxes | lr_neg_clerk_change_tax | **expected fail**: clerk writes `amount` on the 15% tax, refused with an access error |
| 6. Clerk cannot touch closed periods | lr_neg_clerk_lock_date | **expected fail**: clerk runs the lock wizard, refused (access error on `account.change.lock.date`) |
| 6. Accountant closes the month; nothing posts in it | lr_close_month | invoice dated 2026-08-10 posted; accountant locks 2026-08-31: company `fiscalyear_lock_date` = 2026-08-31; accountant posts an invoice dated 2026-08-20: `invoice_date` = 2026-08-20, `date` ≠ 2026-08-20 (moved out of August) |
| 6. Nobody changes a closed month, accountant included | lr_neg_accountant_edit_closed | **expected fail**: accountant resets the 2026-08-10 invoice to draft, refused with "You cannot add/modify entries prior to and inclusive of" |
| 6. Reopen on purpose | lr_reopen_month | accountant lowers the lock to 2026-07-31 for the accountant only, for 1 hour, with a reason: an `account.lock_exception` `state` = `active`; an invoice dated 2026-08-25 then posts with `date` = 2026-08-25. Runs last |

## Not covered by this plan
- Sending invoices by email: needs an outgoing mail server; the send wizard is not exercised.
- Invoices typed by hand for European customers do not default to EUR (see Decision 4); a EUR sale journal would
  be the next step if the business invoices without orders.
- Bank statement import (CAMT, OFX, CSV) or bank synchronization: the scenarios create statement lines directly.
- Renaming company 1 to "Lumen Ridge Studios" and its real tax rate: left as the demo's 15% "standard sales tax".

## Glossary
- **Fiscal position**: rule that swaps taxes (and accounts) for some customers or vendors; `account.fiscal.position`.
- **Early payment discount**: discount granted when the customer pays before a date; fields on `account.payment.term`.
- **Down payment**: partial invoice of a sales order before delivery, deducted on the final invoice.
- **Analytic plan / account**: management dimension (project, department) and its values; `account.analytic.plan`, `account.analytic.account`.
- **Lock date**: date up to which entries can no longer be added or changed; `res.company.fiscalyear_lock_date`.
- **Lock exception**: temporary, audited reopening of a locked period for a user or everyone; `account.lock_exception`.
- **Exchange difference**: gain or loss booked when a foreign-currency invoice is paid at another rate; `account.partial.reconcile.exchange_move_id`.
