---
title: Invoicing vs Accounting apps (modules and access groups)
area: accounting
odoo_version: 20.0
edition: enterprise
source: [odoo/addons/account/__manifest__.py@20.0, enterprise/account_accountant/__manifest__.py@20.0, enterprise/accountant/__manifest__.py@20.0, enterprise/accountant/__init__.py@20.0, enterprise/accountant/security/accounting_security.xml@20.0, enterprise/accountant/models/account_move.py@20.0, odoo/addons/account/security/account_security.xml@20.0, odoo/addons/account/models/account_payment.py@20.0, odoo/addons/account/models/res_config_settings.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account, account_accountant, accountant]
models: [ir.module.module, res.groups, res.users, res.config.settings]
settings: [module_account_accountant]
---

## When to use
- Decide this first for any accounting requirement, because the two apps behave differently on payments and give
  users different rights:
  - **Invoicing only** (customer invoices, vendor bills, payments, no bookkeeping): `account` (Community, shown as
    "Invoicing"), plus `account_accountant` in Enterprise (also shown as "Invoicing", `auto_install`).
  - **Full accounting** (bank reconciliation, reports, closing, analytic for bookkeepers, assets, ...): the
    Enterprise application `accountant` ("Accounting"), which depends on `account_reports`.
- If the requirement mentions bank reconciliation, financial reports, tax returns or bookkeepers, plan an
  `install_modules` op for `accountant`; on Community there is no equivalent app.

## Configuration
- Module names and app titles (manifests @20.0): `account` = "Invoicing" (application), `account_accountant` =
  "Invoicing" (Enterprise, `auto_install`), `accountant` = "Accounting" (Enterprise, application, depends on
  `account_reports`). On the live template DB `account` and `account_accountant` are installed and `accountant` is
  **not**.
- The settings field `module_account_accountant` (labelled "Accounting") installs `account_accountant`, which on an
  Enterprise database is already there; it does **not** install `accountant`. Install `accountant` with
  `install_modules`.
- Groups (`account/security/account_security.xml@20.0`): `account.group_account_invoice` ("Invoicing"),
  `account.group_account_readonly`, `account.group_account_basic`, `account.group_account_user` ("Show Full
  Accounting Features"), `account.group_account_manager` ("Administrator"). `accountant` renames readonly/user to
  "Read-only"/"Bookkeeper", gives `account.group_account_user` to `base.user_admin` and `base.user_root`, and makes
  `group_account_manager` imply `group_account_user` instead of `group_account_invoice`
  (`accountant/security/accounting_security.xml@20.0`).
- Payment behaviour: `accountant` overrides `account.move._get_invoice_in_payment_state` to return `in_payment`
  (`enterprise/accountant/models/account_move.py@20.0`); `account.payment.create` forces an outstanding account
  (and therefore a journal entry) on every payment only when that hook does not return `in_payment`
  (`account_payment.py@20.0`).

## How to verify
- `ir.module.module` `state` of `account`, `account_accountant`, `accountant`.
- Admin rights: `res.users` search `[["login", "=", "admin"], ["all_group_ids", "in", [<group id>]]]` for
  `account.group_account_user` and `account.group_account_manager`. Live template DB (no `accountant`): admin has
  `group_account_manager` and `group_account_invoice`, **not** `group_account_user` or `group_account_readonly`.
- After installing `accountant`, the same search finds `group_account_user` for admin, and `ofa apply` prints a
  `bot groups (...)` line for the groups it copies to `ofa_bot`.

## Pitfalls
- **Names swapped since older versions.** Model memory says "`account_accountant` is the Accounting app". In 20.0
  `account_accountant` is Enterprise Invoicing and the Accounting app is `accountant`.
- Without `accountant`, models restricted to `group_account_user` (for example `account.analytic.plan` is readable
  by "Analytic Accounting" or "Show Full Accounting Features" only) raise `AccessError` for the admin and the bot,
  even with `group_account_manager` (seen live).
- Installing `accountant` changes payment results in scenarios: paid invoices become `in_payment` instead of
  `paid`, and payments on method lines without `payment_account_id` stop creating journal entries (see the payments
  entry).
- `accountant`'s post-init installs `account_reports_cash_basis` for companies in AU, CA and US and starts the
  accounting onboarding for every company with a chart (`accountant/__init__.py@20.0`).

## Alternatives
- Community only: stay on `account` and keep bookkeeping outside Odoo, exporting entries.
- Give selected users `account.group_account_readonly` for audit access instead of full Accounting rights.

## Mexico notes
`l10n_mx_reports` (Enterprise: SAT electronic accounting COA, trial balance, XML pólizas, DIOT) is installed on the
live template DB and depends on `account_reports`, `l10n_mx` and `l10n_mx_edi`, not on `accountant`
(`enterprise/l10n_mx_reports/__manifest__.py@20.0`). See the `l10n_mx` area.
