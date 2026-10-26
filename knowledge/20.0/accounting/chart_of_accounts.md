---
title: Chart of accounts per country (chart templates)
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/chart_template.py@20.0, odoo/addons/account/models/res_config_settings.py@20.0, odoo/addons/account/models/account_account.py@20.0, odoo/addons/account/models/template_generic_coa.py@20.0, odoo/odoo/addons/base/models/res_company.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account]
models: [res.company, account.account, account.chart.template, res.config.settings]
settings: [chart_template]
---

## When to use
- Every company that books invoices needs a chart of accounts (plus the taxes, tax groups, journals and fiscal
  positions that come with it). In Odoo these all come from a **chart template**, one per country (sometimes several
  per country, e.g. `be_comp` / `be_asso`), identified by a code stored on `res.company.chart_template`.
- If the requirement creates a company in a country that has a localization (Mexico, most of Europe, ...), plan
  **nothing** for the chart: creating the company with its `country_id` installs the localization module and loads
  the country's template automatically. Planning an explicit load is redundant.
- If the company is in a country without its own template (Odoo guesses `generic_coa`), the chart is **not** loaded
  automatically; plan it explicitly with the `chart_template` setting.
- If the business wants its own account numbers, load the country template first and then add or rename accounts;
  do not build a chart from nothing, because taxes and journals reference template accounts.

## Configuration
- `res.company.chart_template` (selection of template codes such as `generic_coa`, `mx`, `us`, `ca_2023`, `es_pymes`;
  the list on a given database comes from the installed and installable `l10n_*` modules). Exposed in settings as
  `res.config.settings.chart_template`.
- Automatic load: `res.company.create` calls `install_l10n_modules()` for companies with a country
  (`odoo/odoo/addons/base/models/res_company.py@20.0`); the account override then guesses the template from the
  country (`account.chart.template._guess_chart_template`) and, **unless it is `generic_coa`**, schedules
  `try_loading(template_code, company)` at commit (`odoo/addons/account/models/company.py@20.0`,
  `install_l10n_modules`). The same happens when a company without a country gets one in a `write`.
- Explicit load: a `set_settings` op with `chart_template: "<code>"` for that company. `set_values` calls
  `account.chart.template.try_loading` when the value differs from the company's current one
  (`odoo/addons/account/models/res_config_settings.py@20.0`). Loading requires an administrator
  (`_load` raises `AccessError` otherwise).
- Branches (companies with a `parent_id`) use their root company's template; only company-level data is loaded on
  the branch (`chart_template.py@20.0`, `_load`).
- Accounts: `account.account` with `code`, `name`, `account_type` (selection: `asset_receivable`, `asset_cash`,
  `asset_current`, `asset_non_current`, `asset_prepayments`, `asset_fixed`, `liability_payable`,
  `liability_credit_card`, `liability_current`, `liability_non_current`, `equity`, `equity_unaffected`, `income`,
  `income_other`, `expense`, `expense_other`, `expense_depreciation`, `expense_direct_cost`, `off_balance`),
  `reconcile`, `currency_id`, `tax_ids` (default taxes), `tag_ids`, and `company_ids` (many2many: one account can be
  shared by several companies). `code` is computed from the company-dependent `code_store`, so the same account can
  carry a different code per company.

## How to verify
- `res.company.chart_template` equals the expected code for the company.
- `account.account` search `[["company_ids", "in", [<company id>]]]` returns accounts (on the live template DB the
  generic chart gave company 1 accounts such as `121000 Accounts Receivable`, `101403 Outstanding Receipts`).
- Taxes exist for the company: `account.tax` search `[["company_id", "=", <company id>]]` is non-empty, and
  `res.company.account_sale_tax_id` / `account_purchase_tax_id` are set.
- Journals exist: `account.journal` with `type` `sale`, `purchase`, `bank`, `general` for the company.

## Pitfalls
- **Template record xmlids carry the company id.** Records created by a template get xmlids
  `account.<company_id>_<template id>`, e.g. on the live template DB `account.1_sale_tax_template` (15% sales tax of
  company 1), `account.1_bank` (bank journal), `account.1_account_journal_payment_debit_account_id` (Outstanding
  Receipts). A plan that references them is tied to that company id; for a company the plan creates, look records
  up with `$search` on `company_id` instead.
- Changing `chart_template` on a company **without** journal items deletes the old chart's records (accounts,
  taxes, journals, moves) and loads the new one. With existing journal items nothing is deleted: the new template
  is loaded next to the old one (`chart_template.py@20.0`, `_load`). Choose the chart before posting anything.
- The company currency cannot be changed once journal items exist (`UserError` in `res.company.write`,
  `company.py@20.0`).
- The automatic load runs in a pre-commit hook: within the same transaction the chart is not there yet. Over RPC each
  call is its own transaction, so the next call sees it.
- `generic_coa` is never auto-loaded: a company in a country without a template has no accounts until the
  `chart_template` setting is saved for it.

## Alternatives
- Import accounts from a spreadsheet after loading the template, when the business brings a legacy chart.
- Use a branch (`parent_id`) instead of a separate company when the entity should share the parent's chart, taxes
  and fiscal country.

## Mexico notes
A company created with `country_id = base.mx` loads the `mx` chart automatically (S2 finding F2: 332 accounts on the
spike DB; on the live template DB both Mexican demo companies have `chart_template = 'mx'`). Do not plan a separate
load. See the `l10n_mx` area for the SAT account grouping and the Mexican taxes that come with the chart.
