---
title: Multi-company reporting and consolidation
area: multi_company
odoo_version: 20.0
edition: enterprise
source: [odoo/addons/account/models/account_report.py@20.0, enterprise/account_reports/models/account_report.py@20.0, enterprise/account_reports/models/account_tax.py@20.0, enterprise/account_reports/models/interco_comparison_report.py@20.0, enterprise/account_reports/data/interco_comparison_report.xml@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [account, account_reports]
models: [account.report, account.tax.unit, account.interco.comparison.report.handler]
settings: []
---

## When to use
- If the group wants one balance sheet or P&L over several companies, select those companies together in the
  company switcher and open the report: Enterprise financial reports add up every selected company.
- If several companies file one VAT return together (a VAT group), define a **tax unit** so the tax report covers
  them as one.
- If the companies trade with each other, use the **Interco Comparison** report to check that what company A shows
  as receivable from B matches what B shows as payable to A, before presenting group figures.
- A dedicated consolidation app (consolidation charts, eliminations, ownership percentages) does **not** exist in
  20.0: there is no consolidation module in `enterprise@20.0` (nor in the 19.0 checkout). A requirement for formal
  consolidation with eliminations is not covered by configuration; say so in the plan.

## Configuration
- Modules: `account_reports` (Enterprise; `accountant` depends on it).
- `account.report.filter_multi_company` (field defined in `account`, used by `account_reports`):
  - `selector` ("Use Company Selector"): the report covers `env.companies`, the companies active in the switcher;
  - `tax_units` ("Use Tax Units"): the report covers the selected tax unit, or the active company and its branches
    with the same VAT number. Live: the generic tax report and the tax report use `tax_units`.
- `account.report.currency_translation`: `cta` (default) or `current` ("Use the most recent rate at the date of the
  report"), how amounts of companies in other currencies are converted when the selected companies' currencies
  differ.
- `account.tax.unit` (account_reports): `name`, `country_id`, `vat`, `company_ids`, `main_company_id`,
  `fpos_synced`.
- Interco Comparison: report `account_reports.interco_comparison_report` with handler
  `account.interco.comparison.report.handler` (new in 20.0, absent from the 19.0 checkout). With several companies
  selected it groups the journal items between the active company and the others (lines whose partner is the other
  company's partner) by company, account type and account, and shows the main company's amount, the counterpart's
  and the difference. It warns when only one company is selected.

## How to verify
- `account.report` read `filter_multi_company` and `currency_translation` on the report in question.
- `account.tax.unit` search `[["company_ids", "in", [<id>]]]` lists the units a company belongs to.
- `ir.model.data` `account_reports.interco_comparison_report` exists on the target (live: yes).
- The figures themselves are read in the UI; `ofa` scenarios do not assert report output.

## Pitfalls
- A report run with only one company active in the switcher shows that company alone; "group" figures need all
  companies selected, and the user needs them in `company_ids` (see [user_company_access.md](user_company_access.md)).
- Adding up companies is not consolidation: inter-company balances are not eliminated. Use the Interco Comparison
  report to find them; eliminating them is manual (journal entries) or outside Odoo.
- Some export buttons are disabled unless every branch of the active company is selected
  (`account_reports`, `branch_allowed` on the report buttons).
- Companies in different currencies are converted according to `currency_translation`; the conversion only
  applies when the selected companies have more than one currency (`account_reports`, currency table). Which rates
  `cta` uses for each line was not checked here.

## Alternatives
- Analytic accounting on one company when the "companies" are really cost centers (one set of books, reports by
  analytic plan).
- Export the trial balance of each company and consolidate in a spreadsheet or a dedicated consolidation tool when
  eliminations and ownership percentages are required.
