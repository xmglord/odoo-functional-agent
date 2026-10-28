# Knowledge compendium

Functional configuration knowledge for Odoo, one topic per file, partitioned by Odoo version:

```
knowledge/<odoo_version>/INDEX.md                 links the area indexes
knowledge/<odoo_version>/<area>/INDEX.md          lists the topics of one area
knowledge/<odoo_version>/<area>/<topic>.md        one entry
```

Areas: `sales_crm`, `purchase_inventory`, `accounting`, `multi_company`, `l10n_mx`. Mexican localization is its own
area; the other areas link to it from their `## Mexico notes` sections. Start at [20.0/INDEX.md](20.0/INDEX.md).

The agent reads these files directly (index plus grep). There is no vector store. Each entry says which version and
edition it describes, where every claim comes from, and when it was last checked, so a version change shows exactly
what needs re-checking.

## Entry template

Copy this into `knowledge/<version>/<area>/<topic>.md` (file name in `snake_case`):

```markdown
---
title: Discounts on sales order lines
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales.html, odoo/addons/sale/wizard/res_config_settings.py@20.0]
verified_on: 2026-10-23
verified_against: [source, live]
modules: [sale]
models: [sale.order.line]
settings: [group_discount_per_so_line]
---

## When to use
Decision rules: "if the business does X, configure Y because Z".

## Configuration
The settings, models and fields involved, with their exact technical names.

## How to verify
Read-back checks: which field on which record must hold which value after the change.

## Pitfalls
What goes wrong, and how it shows up.

## Alternatives
Other ways to reach the same business result, and when to prefer them.

## Mexico notes
Optional. What changes for a Mexican company, with links into `l10n_mx`.
```

### Front matter rules

The front matter is a restricted YAML subset so that a stdlib parser can read it:

- one `key: value` per line; no indented lines, no nested maps, no block lists
- lists only in flow form: `[a, b]`
- required keys: `title`, `area`, `odoo_version`, `edition`, `source`, `verified_on`, `verified_against`
- optional keys: `modules`, `models`, `settings` (flow lists)
- `area` and `odoo_version` must match the folders the file lives in
- `edition` is `community` or `enterprise` (the edition the entry needs)
- `source` is a non-empty list of doc URLs or source paths with a branch or commit (`path@20.0`)
- `verified_on` is a `YYYY-MM-DD` date
- `verified_against` lists how the entry was checked: `source` (read in the source code), `docs` (official
  documentation only), `live` (observed on a running demo database)

### Body rules

The five sections `When to use`, `Configuration`, `How to verify`, `Pitfalls` and `Alternatives` are required, as
level-2 headings, in that order. `Mexico notes` is optional. Other headings may be added. `INDEX.md` files are not
entries and are exempt from these checks.

## Writing rules

- Cite a doc URL or a source path @branch for every technical claim. Uncited knowledge is the main way this
  compendium could give confident, wrong advice.
- Give exact technical names: module, model, field, settings field, group and xmlid, as they appear in the code.
- Verification uses read-back fields: say which field on which record proves the change took effect. Never verify
  by calling an RPC helper method.
- Never paste Enterprise code. Cite the Enterprise file path instead.
- Mark what was checked on a live database versus read from source or docs in `verified_against`. Do not write
  `live` unless you observed it.
- Explain for a developer who is new to functional Odoo: say what the business problem is and why the setting solves
  it, not only which box to tick.

## Checking entries

```
bin/ofa stale --lint                       # all entries of the current version
bin/ofa stale --lint --area sales_crm      # one area only
bin/ofa stale --since 2026-10-23           # entries verified before that date
bin/ofa stale                              # entries verified before the Odoo checkout's last commit
```

`--lint` exits 2 on missing or invalid front matter or missing sections. An area index that the version index links
to but that does not exist yet prints a `WARN missing area index` line and does not fail the check. Without `--since`,
the date comes from the local ofa config (the Odoo checkout's HEAD commit date); with no config, pass `--since`.

## Known 20.0 drifts

Places where Odoo 20.0 differs from what older documentation, tutorials or model memory say. Check entries against
these first.

- **Typed `ir.config_parameter` methods.** `set_param`/`get_param` are gone. Use the typed pairs `set_str`/`get_str`,
  `set_int`/`get_int`, `set_float`/`get_float`, `set_bool`/`get_bool`
  (`odoo/odoo/addons/base/models/ir_config_parameter.py@20.0`).
- **`res.users.group_ids`.** The user's groups field is `group_ids` (with `all_group_ids` for groups plus implied
  groups), not `groups_id` (`odoo/odoo/addons/base/models/res_users.py@20.0`). Already so in 19.0; listed because
  older guides and model memory say otherwise.
- **Access rights are `ir.access`.** The access-rights model is `ir.access` (`name`, `model_id`, `group_id`,
  `operation`, ...), not `ir.model.access` with its `perm_read`/`perm_write`/... columns
  (`odoo/odoo/addons/base/models/ir_access.py@20.0`).
- **No `sale.order.require_payment`.** The order has no "online payment required" flag any more. It has
  `prepayment_percent`, computed from the company: the company's `prepayment_percent` when `portal_confirmation_pay`
  is set, else 0 (`odoo/addons/sale/models/sale_order.py@20.0`, `_compute_prepayment_percent`).
- **`product_and_description` on sales order lines.** The order line list shows product and description in a single
  `product_and_description` column that groups `product_template_id`/`product_id` and `name`
  (`odoo/addons/sale/views/sale_order_views.xml@20.0`). It is a view column, not a model field: plans and checks still
  use the underlying fields.
- **Tax mapping lives on the tax.** Fiscal position mapping is no longer edited on the fiscal position form. Each tax
  carries `fiscal_position_ids` and `original_tax_ids` (the taxes it replaces)
  (`odoo/addons/account/models/account_tax.py@20.0`). Already so in 19.0; listed because older guides and model
  memory say otherwise.
- **A Mexican company loads the `mx` chart automatically.** Creating a company with country Mexico triggers the
  localization install and loads the `mx` chart of accounts for it
  (`odoo/addons/account/models/company.py@20.0`, `install_l10n_modules`). Do not plan a separate chart load for it.
  Already so in 19.0; listed because older guides and model memory say otherwise.
- **Unit of measure on moves and purchase lines is `uom_id`.** `stock.move.product_uom`,
  `stock.move.line.product_uom_id` and `purchase.order.line.product_uom_id` are now `uom_id`
  (`odoo/addons/stock/models/stock_move.py@20.0`, `stock_move_line.py`,
  `odoo/addons/purchase/models/purchase_order_line.py@20.0`). `sale.order.line` and `account.move.line` keep
  `product_uom_id`.
- **Product tracking is `store_by`.** `product.template.store_by` (`untracked`, `quantity`, `lot`, `serial`) is the
  "Tracking" field. `tracking` is now only `lot` or `serial`, with `False` for a product tracked by quantity; the
  value `'none'` is gone (`odoo/addons/stock/models/product.py@20.0`).
- **Record rules are `ir.access` too.** `ir.rule` (with `domain_force`) is gone. A record rule is an `ir.access`
  record with a `domain`; its computed `kind` is `restriction` (it narrows access) or `permission`, and a rule
  without `group_id` applies to everyone (`odoo/odoo/addons/base/models/ir_access.py@20.0`).
- **No `ir.attachment.datas`.** The file content is `raw` (binary) on `ir.attachment`; `datas` (base64) is gone
  (`odoo/odoo/addons/base/models/ir_attachment.py@20.0`).
- **No `base_vat` module.** VAT number checks (`_check_vat`, `check_vat_<country>`) live in `base`
  (`odoo/odoo/addons/base/models/res_partner.py@20.0`); do not plan an install of `base_vat`.
- **Inter-company rules have no user or warehouse fields.** `res.company.intercompany_user_id`,
  `intercompany_warehouse_id` and `intercompany_receipt_type_id` and their settings fields are gone; the generated
  documents are created as the superuser in the receiving company
  (`enterprise/account_inter_company_rules/models/account_move.py@20.0`).
- **A currency rate applies from the day after its date.** `res.currency._get_rates` looks up the latest rate with
  `name < date`, where 19.0 used `name <= date` (`odoo/odoo/addons/base/models/res_currency.py@20.0`). A rate dated
  the same day as a document is not used for that document.
