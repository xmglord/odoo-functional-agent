---
title: Companies vs branches (company hierarchy)
area: multi_company
odoo_version: 20.0
edition: community
source: [odoo/odoo/addons/base/models/res_company.py@20.0, odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/chart_template.py@20.0, odoo/addons/stock/models/res_company.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [base, account, stock]
models: [res.company, stock.warehouse]
settings: []
---

## When to use
- If the legal entities are separate (own tax id, own books, own currency, possibly another country), create one
  **company** per entity: a `res.company` with no `parent_id`. Each has its own chart of accounts, taxes, journals
  and documents; nothing accounting-related is shared.
- If one legal entity has several operating units (stores, regional offices, departments) that need their own
  documents and numbering but share the entity's chart of accounts, taxes and currency, create them as **branches**:
  a `res.company` whose `parent_id` is the entity. Branch users see the parent's accounts, taxes, journals, products
  and contacts (see [shared_vs_company_records.md](shared_vs_company_records.md)).
- A holding with subsidiaries in several countries is several root companies; a subsidiary with offices is a root
  company with branches.

## Configuration
- `res.company`: `name` (unique), `parent_id` (the parent company; empty for a root company), `child_ids`
  ("Branches"), `all_child_ids` (branches including archived ones), computed `parent_ids` (the chain from the root
  down to this company) and `root_id`, `partner_id` (the company's contact), `country_id`, `currency_id`.
- Creating a company (`res.company.create`):
  - creates its contact `res.partner` (with `company_id` empty, so every company can see it) and sets `partner_id`;
  - links the new company to the **creating user** and to the superuser (`company_ids`), and to nobody else;
  - with a `country_id`, calls `install_l10n_modules`, which installs the country's localization and loads its chart
    (live: a United States company got `chart_template = 'us'` and its own journals, taxes and accounts);
  - for a branch, copies the root's delegated fields first: `currency_id` (base) plus `fiscalyear_last_day`,
    `fiscalyear_last_month`, `account_storno` and `tax_exigibility` (account,
    `_get_company_root_delegated_field_names`).
- Branch chart: `account` loads the root's `chart_template` for the branch, but for a branch it loads only the
  company-level data (`chart_template.py`, `_load`: `data = {'res.company': ...}` when `company.parent_id`). Live,
  the branch had `chart_template = 'us'` and no journals or taxes of its own; it uses the root's.
- Warehouses: `stock` creates per-company locations, sequences, operation types and rules for a new company, but
  **no `stock.warehouse`** (it only does so under tests, `res_company.py` `create`). A plan that needs stock moves or
  inter-company sales in the new company creates a `stock.warehouse` with `company_id` = the company (an
  `upsert_record` with the op's `company` set to it). Same in 19.0.
- In a plan: one `upsert_record` on `res.company` per company, keyed (`key`) and matched by `name`; the branch op
  `depends_on` the parent's op and refers to it with `{"$ref": "__ofa__.<key>"}` in `parent_id`.

## How to verify
- `res.company` of the branch: `parent_id` = the parent, `root_id` = the root; on the parent, `child_ids` contains
  the branch.
- `chart_template` on both is the root's code (`us`, `mx`, ...); `currency_id` is the same on both.
- `account.journal` search `[["company_id", "=", <branch id>]]` is empty right after creating a branch (it uses the
  root's journals); for a new root company it lists Sales, Purchases, Bank, Miscellaneous Operations, ...
- `stock.warehouse` search `[["company_id", "=", <id>]]`: empty until the plan creates one.

## Pitfalls
- **The hierarchy cannot be changed.** `res.company.write` with `parent_id` raises `UserError` "The company
  hierarchy cannot be changed." (even to the same value). Decide company vs branch before creating it; a re-apply
  must leave `parent_id` alone (an `upsert_record` writes only differing fields, so an unchanged `parent_id` is not
  written).
- `name` is unique: re-running a plain `create` of the same company fails; use `upsert_record` with `match` on
  `name`.
- A company created by one user is not visible to other users (not even the admin) until they get it in
  `company_ids` (see [user_company_access.md](user_company_access.md)). Live: after the plan created two companies,
  `ofa_bot` had them and `admin` did not.
- Archiving a company also archives its branches (`res.company.write`).
- Lock dates of a parent company also apply to its branches (accounting area, lock dates entry).
- Creating a company with a country installs that country's localization module if it is missing, which can take a
  while and pulls in its dependencies.

## Alternatives
- Analytic accounting (plans and accounts per store or department) when the units do not need their own documents,
  numbering or access restrictions: one company, analytic distributions on the lines.
- Several warehouses in one company when the split is only physical (stock), not about documents or access.
- Separate databases when the entities share nothing and must never see each other's data (no inter-company flows,
  no shared contacts or products, separate administrators).

## Mexico notes
A company with country Mexico loads the `mx` chart on creation, and a branch of it gets the same `chart_template`
and uses the root's accounts and taxes (same mechanism as above; not checked live for `mx`). Each Mexican legal
entity (own RFC) is its own root company. See the `l10n_mx` area for Mexican fiscal data.
