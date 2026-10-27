---
title: Mexican chart of accounts loaded on company creation
area: l10n_mx
odoo_version: 20.0
edition: community
source: [odoo/odoo/addons/base/models/res_company.py@20.0, odoo/addons/account/models/company.py@20.0, odoo/addons/l10n_mx/models/template_mx.py@20.0, odoo/addons/l10n_mx/data/template/account.tax-mx.csv@20.0, odoo/addons/l10n_mx/data/template/account.fiscal.position-mx.csv@20.0, enterprise/l10n_mx_edi/models/account_chart_template.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [l10n_mx, account]
models: [res.company, account.chart.template, account.tax, account.fiscal.position, account.journal]
settings: [chart_template]
---

## When to use
- If the business opens a Mexican company (a subsidiary of a holding, or the only company of the database), create
  the `res.company` with `country_id = base.mx` and its currency `base.MXN`. Odoo then installs the localization
  modules for Mexico and loads the `mx` chart of accounts for that company by itself, because the localization is
  what gives the company SAT-coded accounts, the Mexican taxes and the cash-basis journal it needs before any
  invoice. Do not plan a separate chart load.
- If a company already has another chart (`chart_template` set) or has entries, it does not get the `mx` chart
  automatically; changing a chart after accounting started is not supported in the normal flow (see the accounting
  chart entry).
- A branch (`parent_id` set) takes its parent's `chart_template` instead of guessing from the country.

## Configuration
- `res.company.create` (and `write` when the country changes) calls `install_l10n_modules`
  (`odoo/odoo/addons/base/models/res_company.py@20.0`), which installs the country's uninstalled localization
  modules (`uninstalled_l10n_module_ids`).
- The `account` override (`odoo/addons/account/models/company.py@20.0`, `install_l10n_modules`) then, for each
  company with a country and no `chart_template`, picks `parent_id.chart_template` or
  `account.chart.template._guess_chart_template(country)` and calls `try_loading(template_code, company)` in a
  pre-commit hook: the chart is loaded when the transaction that created the company commits, not inside it.
- What the `mx` template sets (`odoo/addons/l10n_mx/models/template_mx.py@20.0`):
  - company: `account_fiscal_country_id = base.mx`, `anglo_saxon_accounting = True`,
    `display_invoice_amount_total_words = True`, `tax_cash_basis_journal_id` = the "Effectively Paid" journal (code
    `CBMX`), `account_sale_tax_id` = IVA 16% sales (`tax12`), `account_purchase_tax_id` = IVA 16% purchases
    (`tax14`), income/expense, receivable/payable and exchange accounts, `l10n_mx_income_return_discount_account_id`
    and `l10n_mx_income_re_invoicing_account_id`; 9-digit account codes (`code_digits`).
  - journals: the standard ones plus `CBMX` ("Effectively Paid") and a Cash journal.
  - taxes and tax groups from `odoo/addons/l10n_mx/data/template/account.tax-mx.csv@20.0` (see the IVA entry), plus
    the "Local Tax" pair from `enterprise/l10n_mx_edi/data/template/account.tax-mx.csv@20.0` when `l10n_mx_edi` is
    installed.
  - fiscal positions: "MX Domestic", "Foreign Customer", "Freight", "Honorarium", "Lease"
    (`account.fiscal.position-mx.csv`).
- With `l10n_mx_edi` installed, the template also sets `l10n_mx_edi_factoring_account_id`
  (`enterprise/l10n_mx_edi/models/account_chart_template.py@20.0`).
- The template records get xmlids `account.<company_id>_<template id>`, e.g. `account.4_tax12` for IVA 16% sales
  of company 4 (seen on the live template DB).

## How to verify
- On the new company: `chart_template = 'mx'`, `account_fiscal_country_id = base.mx`, `currency_id = base.MXN`,
  `tax_exigibility = True`, `tax_cash_basis_journal_id` set, `account_sale_tax_id` and `account_purchase_tax_id`
  set. Observed live on a company created by the l10n_mx fixture plan.
- `account.tax` search with `company_id` = the company, `type_tax_use = 'sale'`, `name in ('16%', '8%', '0%',
  'Exento')` returns 4 records; `account.fiscal.position` has the five MX positions; `account.journal` has code
  `CBMX`.
- Scenario `scenarios/20.0/l10n_mx/l10n_mx_company_chart_autoload.json` runs these checks.

## Pitfalls
- `res.company.country_id` is not stored in 20.0: a domain `[["country_id.code", "=", "MX"]]` on `res.company`
  fails with "Field has no SQL representation because it is not stored". Filter on `partner_id.country_id.code` or
  `account_fiscal_country_id`.
- The chart loads at commit time. A plan that creates the company and, in the same call, expects its taxes will not
  see them; separate operations (separate requests) do.
- The created company is new to every user: the bot user only reaches it because `ofa` adds created companies to
  its `company_ids`; real users need it added to theirs (see the multi-company area).
- The new company has no RFC (`vat`), no CSD certificate and no fiscal regime from the chart. It cannot stamp until
  those are set (see the fiscal data and CFDI configuration entries).
- Taxes are referenced by company-specific xmlids (`account.<id>_tax12`); a plan written for company 4 does not work
  for another company id. Inside a plan, use `$search` on `company_id` and `name`/`type_tax_use`.

## Alternatives
- Load the chart by hand from Accounting settings (the "Fiscal Localization" / `chart_template` choice) for a
  company created without a country; this is the same `try_loading`.
- A branch of a Mexican company (`parent_id`) shares the parent's chart instead of loading its own.

## Mexico notes
This entry is the Mexico note for the accounting chart entry
([chart_of_accounts.md](../accounting/chart_of_accounts.md)). Taxes: [iva_and_withholdings.md](iva_and_withholdings.md).
