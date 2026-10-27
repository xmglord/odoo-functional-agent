---
title: Per-company vs global settings
area: multi_company
odoo_version: 20.0
edition: community
source: [odoo/odoo/addons/base/models/res_config.py@20.0, odoo/addons/base_setup/models/res_config_settings.py@20.0, odoo/odoo/addons/base/models/ir_default.py@20.0, enterprise/sale_purchase_inter_company_rules/models/res_config_settings.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [base, base_setup]
models: [res.config.settings, res.company, ir.default, ir.config_parameter, res.groups]
settings: [company_id, is_root_company]
---

## When to use
- Before writing a `set_settings` op in a database with several companies, check which kind each settings field is:
  some apply to one company, most apply to the whole database. A requirement such as "only the subsidiary uses X"
  is possible only for the per-company kind.

## Configuration
`res.config.settings` is a transient form; saving it (`execute`) dispatches each field by its kind
(`res_config.py`, `_get_classified_fields`):

| Field kind | How to recognise it | Scope |
|---|---|---|
| related to the company | `related='company_id.<field>'` | **per company**: written on `res.company` of the settings' `company_id` |
| `group_*` | boolean with `implied_group` | **global**: the group is implied on `base.group_user` (or the field's `group`) for every user of every company |
| `module_*` | boolean | **global**: installs or uninstalls the module |
| `default_*` | `default_model` attribute | **global**: `ir.default.set` with `company_id = False` |
| config parameter | `config_parameter` attribute | **global**: one `ir.config_parameter` for the database |

- `res.config.settings.company_id` (base_setup) defaults to `env.company`, the first id of `allowed_company_ids`.
  `is_root_company` is false when that company is a branch; the accounting settings view then hides the fiscal
  localization block and makes `vat_disabled` read-only (`odoo/addons/account/views/res_config_settings_views.xml@20.0`).
- In a plan, a `set_settings` op with `company` = `{"$ref": <company>}` opens and saves the settings in that
  company's context, so a per-company field lands on that company. Live: `intercompany_generate_sales_orders`
  (related to `res.company.intercompany_generate_sales_orders`) saved with the subsidiary's `company` was true on the
  subsidiary and stayed false on the main company and on the subsidiary's branch.
- To find the kind of a field: `ofa inspect --target <t> res.config.settings --fields <name>` shows its type; the
  source (`res_config_settings.py` of the module) shows `related=`, `implied_group=`, `default_model=` or
  `config_parameter=`.

## How to verify
- Per-company field: read the underlying `res.company` field on each company; only the target company changed.
- `group_*`: read `implied_ids` of `base.group_user` (contains the group), or `all_group_ids` of a user.
- `default_*`: `ir.default` search on the field, `company_id = false`.
- Config parameter: `ir.config_parameter` `get_str`/`get_bool` (typed methods in 20.0).

## Pitfalls
- A `group_*` setting saved "in the subsidiary" still switches the feature on for every company: there is no
  per-company version: `execute` applies the implied group to the whole user group (source; not tested live here).
- `set_settings` without `company` uses the bot's default company (`company_id` of `ofa_bot`, the demo main
  company), not "all companies". A per-company setting for several companies needs one op per company.
- On a branch, fields delegated to the root (currency, fiscal year end, storno, tax exigibility) are copied from the
  root and cannot be set separately (see [companies_and_branches.md](companies_and_branches.md)).
- Saving settings runs `execute` over every field of the form, not only the ones in `values`. `ofa` creates the
  form with `values` only, so the other fields take their current values from `default_get` and keep them.

## Alternatives
- Write the `res.company` field directly with an `upsert_record` on the company (key it and set the field) when the
  setting is a plain company field; same effect, without opening the settings form.
- Company-dependent fields on partners or products (see
  [shared_vs_company_records.md](shared_vs_company_records.md)) for per-company values on shared records.
