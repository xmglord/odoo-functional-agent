---
title: Analytic accounting (plans, accounts, distributions)
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/analytic/models/analytic_plan.py@20.0, odoo/addons/analytic/models/analytic_account.py@20.0, odoo/addons/analytic/models/analytic_distribution_model.py@20.0, odoo/addons/analytic/models/analytic_mixin.py@20.0, odoo/addons/analytic/models/res_config_settings.py@20.0, odoo/addons/analytic/security/analytic_security.xml@20.0, odoo/addons/account/models/account_analytic_plan.py@20.0, odoo/addons/account/models/account_analytic_distribution_model.py@20.0, odoo/addons/account/models/account_move_line.py@20.0, odoo/addons/account/models/res_config_settings.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [analytic, account]
models: [account.analytic.plan, account.analytic.account, account.analytic.applicability, account.analytic.distribution.model, account.analytic.line, account.move.line, res.config.settings]
settings: [group_analytic_accounting]
---

## When to use
- If management wants profit or cost **per project, department, branch, campaign** (dimensions that are not
  accounts in the chart), use analytic accounting: each dimension is an analytic **plan**, each value an analytic
  **account**, and journal items carry a percentage **distribution** over those accounts.
- If every expense must be assigned to a department, make that plan `mandatory` for bills, because posting then
  fails until the line has a 100% distribution.
- If a customer, product or product category always goes to the same analytic account, use a **distribution model**
  so the distribution is filled automatically.
- If the requirement is legal reporting (balance sheet, tax), analytic is the wrong tool: use accounts.

## Configuration
- Switch: settings field `group_analytic_accounting` (implies `analytic.group_analytic_accounting`). Its onchange
  also ticks `module_account_accountant` (`account/models/res_config_settings.py@20.0`,
  `onchange_analytic_accounting`); an onchange does not run in a `set_settings` op, so state it explicitly if wanted.
- `account.analytic.plan`: `name`, `parent_id` (sub-plans; `root_id` computed), `description`, `sequence`, `color`,
  `default_applicability` (`optional`, `mandatory`, `unavailable`; company dependent), `applicability_ids`.
- `account.analytic.applicability`: `analytic_plan_id`, `business_domain` (`general`, `invoice`, `bill`, plus
  `sale_order` / `purchase_order` when those apps are installed; the live template DB lists all five),
  `applicability` (`optional`, `mandatory`, `unavailable`), `account_prefix` (financial account code prefixes),
  `product_categ_id`, `company_id`.
- `account.analytic.account`: `name`, `code`, `plan_id`, `root_plan_id`, `company_id` (empty = shared),
  `partner_id`, `active`; computed `balance`, `debit`, `credit`.
- Distribution: `analytic_distribution` (JSON) on `account.move.line` (and other `analytic.mixin` models such as
  order lines): keys are analytic account ids as strings (several plans' accounts joined by commas in one key),
  values are percentages, e.g. `{"7": 100}` or `{"7,12": 60, "8": 40}`.
- `account.analytic.distribution.model`: `analytic_distribution`, `partner_id`, `partner_category_id`,
  `product_id`, `product_categ_id`, `account_prefix`, `company_id`, `sequence`. Matching models prefill the
  distribution of new lines (`_get_distribution`, used by `account.move.line._compute_analytic_distribution`).
- Posting creates `account.analytic.line` records (`account_id`, `amount`, `date`, `name`, `move_line_id`) from the
  distribution (`account.move.line._create_analytic_lines`).

## How to verify
- Setting: `analytic.group_analytic_accounting` among the implied groups of `base.group_user`; the settings field
  reads `true`.
- Plan: `account.analytic.plan` with the expected `default_applicability` / `applicability_ids` (business domain and
  applicability).
- Distribution model: `account.analytic.distribution.model` with the partner/product criteria and
  `analytic_distribution`.
- Posted invoice or bill: each product line's `analytic_distribution`, and `account.analytic.line` records whose
  `move_line_id` is that line with the expected `account_id` and `amount`.

## Pitfalls
- **Reading plans needs a group.** On the live template DB the bot (with the admin's groups, analytic not enabled)
  got `AccessError` reading `account.analytic.plan` ("allowed for the following groups: Analytic Accounting, Show
  Full Accounting Features" = `account.group_account_user`), while `account.analytic.account` was readable. Enable
  `group_analytic_accounting` before plans or scenarios touch plans.
- A `mandatory` plan blocks posting of lines without a full distribution ("One or more lines require a 100%
  analytic distribution.", `_validate_analytic_distribution`, for `product` lines only).
- Archived analytic accounts block posting ("You cannot post an entry with an archived analytic account").
- The distribution keys are ids, not names or codes: a plan cannot write a distribution with `$ref` inside a JSON
  key. Create the analytic accounts first, then write the distribution in a later step with the ids read back, or
  use a distribution model keyed by partner/product.
- Plans are company independent; `default_applicability` is company dependent, so set it with the op's `company`.

## Alternatives
- Separate journals or accounts when the split is legal or fiscal, not managerial.
- Budgets (`account_budget`, Enterprise) on top of analytic accounts for planned vs actual.
- Project and timesheet apps create and use analytic accounts on their own (one per project).

## Mexico notes
Nothing Mexico-specific was checked for analytic accounting. SAT electronic accounting is built from the financial
accounts and their grouping, so keep fiscal splits in accounts, not analytic; see the `l10n_mx` area.
