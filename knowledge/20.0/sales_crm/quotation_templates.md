---
title: Quotation templates and optional lines
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales/sales_quotations/quote_template.html, odoo/addons/sale_management/models/sale_order_template.py@20.0, odoo/addons/sale_management/models/sale_order_template_line.py@20.0, odoo/addons/sale_management/models/sale_order.py@20.0, odoo/addons/sale_management/models/sale_order_line.py@20.0, odoo/addons/sale_management/views/sale_management_menus.xml@20.0, odoo/addons/sale/models/product_template.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [sale_management]
models: [sale.order.template, sale.order.template.line, sale.order, sale.order.line, product.template]
settings: []
---

## When to use
- If salespeople send the same kind of offer again and again (a standard package, a service bundle), create a
  `sale.order.template`, because choosing it on a quotation fills the lines, terms, validity and signature/payment
  rules in one step and keeps offers consistent.
- If the customer should be able to add extras on the online quotation (accessories, extended warranty), put them in
  an **optional section** of the template: a section line with `is_optional = True` followed by product lines with
  quantity 0. The customer sets the quantity in the portal.
- If a confirmed order of this kind should trigger a specific confirmation email, set `mail_template_id` on the
  template.
- If different teams sell different packages, restrict templates with `team_ids`.

## Configuration
- Module `sale_management` (the "Sales" app). In 20.0 there is **no settings checkbox** for templates: the model
  and the menu "Sales > Configuration > Templates" (`sale_management.sale_order_template_menu`) are available as
  soon as the module is installed, and `sale.order.sale_order_template_id` is on the order form for every user.
- `sale.order.template`: `name`, `active`, `company_id`, `currency_id`, `sequence`, `note` (terms and conditions),
  `template_type` (`quotation` / `section`; only `quotation` templates can be picked on an order),
  `number_of_days` (quotation validity), `require_signature`, `prepayment_percent` (both default from the company's
  online signature/payment settings), `mail_template_id`, `journal_id` (company dependent), `share_template`,
  `team_ids`, `sale_order_template_line_ids`.
- `sale.order.template.line`: `sale_order_template_id`, `sequence`, `product_id`, `name`, `product_uom_qty`,
  `product_uom_id`, `display_type` (`line_section`, `line_subsection`, `line_note`), `is_optional`,
  `collapse_prices`, `collapse_composition`, and for lines without product `price_unit`, `discount`, `tax_ids`.
- On the order: `sale_order_template_id`. The onchange `_onchange_sale_order_template_id` replaces `order_line`
  with the template lines; computes copy `note`, `require_signature`, `prepayment_percent`, `validity_date` and
  `journal_id` from the template.
- `sale.order.line.is_optional` (added by `sale_management`) marks optional sections; lines under them can be edited
  on the portal.
- `product.template.optional_product_ids` (module `sale`) is a different feature: cross-sell suggestions in the
  product configurator and the shop.

## How to verify
- Template: `sale.order.template` with `template_type == 'quotation'`, `active` true, and its
  `sale_order_template_line_ids` (read `product_id`, `product_uom_qty`, `display_type`, `is_optional`).
- Optional section: a template line with `display_type == 'line_section'` and `is_optional == True`, followed by
  lines with `product_uom_qty == 0`.
- On an order created from the template through the UI: `sale_order_template_id` set, `order_line` mirrors the
  template, `validity_date` equals order date plus `number_of_days` (when > 0).

## Pitfalls
- **No `group_sale_order_template` in 20.0.** Older versions and the 20.0 docs page describe a "Quotation
  Templates" checkbox and a "Default Template" field in the settings. Neither exists in the 20.0 source
  (`odoo/addons/sale/wizard/res_config_settings.py@20.0`, `odoo/addons/sale_management/wizard/res_config_settings.py@20.0`),
  and `res.company` has no default template field. Plans must not set them.
- **No `sale.order.option` / `sale.order.template.option` in 20.0.** The older "Optional Products" tab is replaced by
  optional sections (`is_optional`) inside the normal lines.
- Lines are filled by an **onchange**. Creating a `sale.order` over JSON-2 with only `sale_order_template_id` does
  not run onchanges, so the order has no lines. Scenarios must create the lines explicitly or copy them from the
  template lines.
- `template_type = 'section'` templates are saved sections ("Save as template" on a section line) and are hidden
  from the order's template field.
- `require_signature` and `prepayment_percent` on the template are computed from the company when the template is
  created; changing the company setting later does not update existing templates.

## Alternatives
- For a fixed bundle sold as one product, use a combo product (`product.template.type = 'combo'`) instead of a
  template.
- For cross-selling in the configurator or eCommerce, use `optional_product_ids` on the product.
- For a designed PDF quotation, `module_sale_pdf_quote_builder` installs the PDF quote builder.
