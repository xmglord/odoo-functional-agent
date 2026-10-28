---
title: Multi-currency (rates, foreign-currency documents, exchange differences)
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/odoo/addons/base/models/res_currency.py@20.0, odoo/addons/base_setup/models/res_config_settings.py@20.0, odoo/addons/account/models/res_config_settings.py@20.0, odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/account_move.py@20.0, odoo/addons/account/models/account_move_line.py@20.0, odoo/addons/account/models/account_partial_reconcile.py@20.0, enterprise/currency_rate_live/models/res_config_settings.py@20.0, enterprise/currency_rate_live/views/service_cron_data.xml@20.0]
verified_on: 2026-10-28
verified_against: [source, live]
modules: [base, account, currency_rate_live]
models: [res.currency, res.currency.rate, res.company, account.move, account.move.line, account.journal, account.partial.reconcile, res.config.settings]
settings: [group_multi_currency, currency_exchange_journal_id, income_currency_exchange_account_id, expense_currency_exchange_account_id, currency_provider, currency_interval_unit, currency_next_execution_date]
---

## When to use
- If the company invoices or buys in a currency other than its own (USD sales from a Mexican company, EUR
  suppliers), **activate that currency** and keep its rates up to date, because every foreign-currency document is
  converted to the company currency at the document date's rate.
- If rates must follow a central bank, enable automatic rates (`currency_rate_live`, Enterprise) with the right
  provider; otherwise enter rates by hand.
- If a foreign-currency invoice is paid at a different rate, Odoo books the **exchange difference** automatically
  at reconciliation; configure which journal and accounts receive it.
- If a bank account is held in a foreign currency, create a bank journal with that `currency_id`.

## Configuration
- Multi-currency is not a switch you turn on: `base.group_multi_currency` is granted to all internal users
  automatically when more than one `res.currency` is active, and removed when only one is left
  (`res.currency._toggle_group_multi_currency`, called on create, unlink and `active` writes). The settings field
  `group_multi_currency` (`base_setup`) shows that state. Plan an `upsert_record` on the currency with
  `active: true` instead of a settings op.
- `res.currency`: `name` (ISO code), `active`, `rounding`, computed `rate` / `inverse_rate` / `rate_date` (for the
  current company and date), `rate_ids`.
- `res.currency.rate`: `name` (the date), `currency_id`, `company_id` (defaults to the root company), `rate`
  (stored technical rate), `company_rate` and `inverse_company_rate` (computed, writable through inverses).
  Meaning, from the code: `res.currency.rate` = units of the currency per 1 unit of the company currency; on the live
  template DB (company currency USD) MXN reads `rate = 18.6664`, `inverse_rate = 0.0536`, i.e. 1 USD = 18.67 MXN.
  `inverse_company_rate` is 1 / `company_rate`, i.e. company currency per 1 unit of the foreign currency.
- Exchange differences (`res.company`, related settings fields of the same name): `currency_exchange_journal_id`
  ("Exchange Gain or Loss Journal", type `general`), `income_currency_exchange_account_id`,
  `expense_currency_exchange_account_id`. Reconciling lines whose company-currency amounts differ creates an
  exchange move in that journal (`account.partial.reconcile.exchange_move_id`).
- Documents: `account.move.currency_id` (computed from the journal currency, else the current value, else the
  company currency; writable), `invoice_currency_rate` (stored rate of the document, from the invoice date);
  lines carry `amount_currency` (document currency) and `balance` (company currency).
- Automatic rates (Enterprise `currency_rate_live`): `res.company.currency_provider` (selection, computed from the
  company country, e.g. `banxico` for MX, `ecb` otherwise), `currency_interval_unit` (`manually`, `daily`,
  `weekly`, `monthly`), `currency_next_execution_date`; same names as settings fields. Fetching is
  `res.company.update_currency_rates`; the scheduled action is `currency_rate_live.ir_cron_currency_update`
  (calls `run_update_currency`).

## How to verify
- Currency active: `res.currency.active` on the currency; `base.group_multi_currency` is then among the groups of
  `base.group_user` (read `res.groups.implied_ids` of `base.group_user`; `_apply_group` links it there).
- A rate exists: `res.currency.rate` search `[["currency_id", "=", <id>], ["name", "=", "<date>"]]`, read `rate`,
  `company_rate`, `inverse_company_rate`.
- Exchange accounts: `res.company.currency_exchange_journal_id`, `income_currency_exchange_account_id`,
  `expense_currency_exchange_account_id` are set (live template DB, company 1: journal "Exchange Difference",
  accounts "Foreign Exchange Gain" / "Foreign Exchange Loss").
- Foreign invoice: `account.move.currency_id`, `invoice_currency_rate`, and on lines `amount_currency` vs `balance`.
- After paying it at another rate: the `account.partial.reconcile` of the invoice has an `exchange_move_id`.

## Pitfalls
- **Field help texts on `res.currency.rate` are misleading.** The `rate` help says "reference-currency units per 1
  unit of this currency", but the computed `rate_string` is "1 <company currency> = <rate> <currency>" and the live
  values above follow that. Write `company_rate` (units of the currency per 1 company-currency unit) or
  `inverse_company_rate` (the other way round) deliberately, and read the result back.
- **A rate applies from the day after its date.** `res.currency._get_rates` takes the latest rate with
  `name < date` (`odoo/odoo/addons/base/models/res_currency.py@20.0`; 19.0 used `<=`). A rate dated the same day as
  an invoice or a payment is not used for it; the previous rate is. A scenario that creates its own rates must date
  them at least one day before the documents. Found live in the T25 example: an EUR invoice dated 2026-09-01 took
  the old demo rate, not the rate dated 2026-09-01.
- Rates are per company root (`company_id`); a rate with no company applies to all. Two rates for the same currency,
  company and date are rejected ("Only one currency rate per day allowed!", unique index `_unique_name_per_day`).
- With `max_cron_threads = 0` on demo targets, `currency_rate_live.ir_cron_currency_update` never runs. Call
  `update_currency_rates` explicitly (a `call_method` op on the company with a `skip_if` on today's rate) or create
  `res.currency.rate` records; fetching needs internet access from the Odoo server.
- The company currency cannot be changed once journal items exist (`company.py@20.0`).
- A journal with `currency_id` forces that currency on its documents (`_compute_currency_id`); do not set it on the
  main sale journal "to allow" foreign invoices, that is not needed.

## Alternatives
- Pricelists in the foreign currency (sales area) when only prices differ and invoices may stay in company currency.
- Manual rates on the document (`invoice_currency_rate` is writable) for contractually fixed rates.

## Mexico notes
For a Mexican company `currency_provider` computes to `banxico` (Bank of Mexico); on the live template DB MXN is
active next to USD. How foreign-currency CFDI documents carry the rate was not checked here; see the `l10n_mx`
area.
