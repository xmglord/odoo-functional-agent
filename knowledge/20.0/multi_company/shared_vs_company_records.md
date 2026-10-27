---
title: Shared vs company-specific records (company_id, record rules, company-dependent fields)
area: multi_company
odoo_version: 20.0
edition: community
source: [odoo/odoo/addons/base/security/ir.access.csv@20.0, odoo/addons/product/security/ir.access.csv@20.0, odoo/addons/account/security/ir.access.csv@20.0, odoo/odoo/orm/models.py@20.0, odoo/addons/account/models/product.py@20.0, odoo/addons/account/models/partner.py@20.0, odoo/odoo/addons/base/models/ir_access.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [base, product, account, sale, purchase, stock]
models: [res.partner, product.template, account.tax, account.journal, sale.order, purchase.order, stock.warehouse, ir.access]
settings: []
---

## When to use
- If a contact or product is used by every company of the group (a shared catalog, a customer that buys from
  several subsidiaries), leave its `company_id` **empty**: every company sees it.
- If a record belongs to one company only (a product only one subsidiary sells, a local supplier), set
  `company_id` to that company: users working in other companies do not see it, and documents of other companies
  cannot use it.
- Taxes, journals, accounts and documents (orders, invoices, pickings) always belong to a company; there is no
  "shared" option for them.

## Configuration
- `company_id` (many2one to `res.company`) is optional on `res.partner` and `product.template`, and required on
  `account.tax`, `sale.order`, `purchase.order`, `stock.warehouse`; on `account.move` it is computed from the
  journal.
  `account.account` uses `company_ids` (many2many) instead.
- Visibility comes from global record rules. In 20.0 they are `ir.access` records with no `group_id`
  (`kind = 'restriction'`) and a `domain`; there is no `ir.rule` model any more. Two shapes matter (read live from
  `ir.access`):
  - `('company_id', 'parent_of', company_ids)`: the record is visible in its company **and in that company's
    branches**. Used by `res.partner` (plus `company_id = False` and partners of internal users,
    `partner_share = False`), `product.template` (plus `company_id = False`), `account.tax`, `account.journal`,
    `account.fiscal.position`, `account.account` (`company_ids`), `product.pricelist`.
  - `('company_id', 'in', company_ids)`: visible only in exactly that company, not in its branches. Used by
    `sale.order`, `purchase.order`, `account.move`, `account.move.line`, `account.payment`, `stock.warehouse`,
    `stock.picking.type`; `stock.location` also allows `company_id = False`.
  - `company_ids` in these domains is the user's active companies (see
    [user_company_access.md](user_company_access.md)).
- Consistency check: many2one fields declared with `check_company=True` must point to a record of the same company
  (or a shared one). On write/create, `_check_company` raises `UserError` "Uh-oh! You've got some company
  inconsistencies here: ... belongs to another company. To avoid a mess, no company crossover is allowed!"
  (checked live: a sales order of the main company with a product restricted to another company).
- Company-dependent fields: one value per company on the same record (stored as a jsonb map keyed by company id,
  `odoo/odoo/orm/fields.py@20.0`). Examples:
  `res.partner.property_account_position_id`, `property_payment_term_id`, `property_account_receivable_id`,
  `property_account_payable_id` (account), `res.partner.property_product_pricelist` (product),
  `product.product.standard_price` (product). Reading or writing them uses the current company (`env.company`, the
  first of `allowed_company_ids`), so a plan sets them with the op's `company` key.
- Product default taxes: a product **without** `company_id` gets the default sales and purchase tax of **every
  company**: the field default takes those of the active companies (`env.companies.account_sale_tax_id`), and
  `product.template.create` links those of all other companies too (`_force_default_tax`, `account/models/product.py`).
  Loading a chart for a new company also adds its default taxes to the existing shared products
  (`chart_template.py`, `_force_default_sale_tax`). Live: a shared product created with only the main company active
  still got five sales taxes, one per company with a chart; the subsidiary-only product got only the subsidiary's.
  Each document only uses the taxes of its own company.

## How to verify
- Read `company_id` on the record: `false` = shared.
- Visibility: as a user whose companies exclude company B, `search` `[["id", "=", <record of B>]]` returns nothing
  (scenario `multi_company_isolation`). Reading the record by id raises `AccessError` instead.
- Rules on the target: `ir.access` search `[["group_id", "=", false], ["model_id.model", "=", "<model>"]]` and read
  `domain`.

## Pitfalls
- Restricting an existing shared product to one company fails once it was sold in another company
  (`_check_sale_product_company` in `sale`, `odoo/addons/sale/models/product_template.py@20.0`); on a contact the
  restriction hides it from the other companies' users. Decide sharing up front.
- Branches see the parent's contacts, products, taxes and journals (`parent_of`), but **not** the parent's orders
  and invoices (`in`). Live: with only the branch active, a product of the parent was visible and a sales order of
  the parent was not.
- A shared product always collects every company's default tax, whatever companies are active when it is created
  (the op's `company` key does not prevent it). To give it other taxes, write `taxes_id` / `supplier_taxes_id` after
  creating it; documents only pick the taxes of their own company anyway.
- A record a user cannot see still blocks uniqueness constraints and can still be referenced by `sudo` code (for
  example inter-company flows).
- Model memory says "record rules are `ir.rule` with `domain_force`": in 20.0 they are `ir.access` with `domain`.

## Alternatives
- One shared record plus company-dependent fields (different fiscal position, payment terms or cost per company)
  instead of duplicating the contact or product per company.
- Product categories or pricelists per company when only prices differ.
- Separate databases when nothing must be visible across entities.
