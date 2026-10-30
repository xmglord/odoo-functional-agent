---
title: Company of a project created from a sale (project templates)
area: multi_company
odoo_version: 20.0
edition: community
source: [odoo/addons/sale_project/models/sale_order.py@20.0, odoo/addons/sale_project/models/sale_order_line.py@20.0, odoo/addons/sale_project/models/product_template.py@20.0, odoo/addons/project/models/project_project.py@20.0]
verified_on: 2026-10-30
verified_against: [source, live]
modules: [sale_project, project]
models: [project.project, product.template, account.analytic.account]
settings: []
---

## When to use
- A service product creates a project when the order is confirmed, in a database with more than one company, and
  the project and its analytic account must belong to the order's company.
- The requirement mentions a project template on a service product (`service_tracking` `project_only` or
  `task_in_project`), or projects or analytic accounts that appear with no company after a sale.

## Configuration
- Set `company_id` on the project template (`project.project` with `is_template = True`) to the company that sells the
  product. `product.template.project_template_id` is `company_dependent`, so it holds one template per company: each
  selling company needs its own template, with its own `company_id`, set under that company.
- Why: a project created from a sale takes the company of its **template**, not of the order, when it is the order's
  only project. `sale.order._action_confirm` (`sale_project/models/sale_order.py`) runs
  `project.sudo().company_id = project_template.sudo().company_id` when `len(order.project_ids) == 1` and the line has a
  template. The project was created correctly just before: `_timesheet_create_project_prepare_values` passes the
  order line's `company_id`, and `_prepare_analytic_account_data` gives the account the order's company.
- A template with no company therefore empties the project's company, and `project.project._inverse_company_id`
  then writes that empty value to the analytic account (`account.company_id = project.company_id or
  project.partner_id.company_id`).

Measured live on 20.0, 2026-10-30, order of company B, customer with no company, the active company either B or the
main company (the result did not depend on it):

| Case | Project company | Account company |
|---|---|---|
| One line, template with no company | empty | empty |
| One line, template of company B | B | B |
| One line, no template | B | B |
| Two lines, two templates with no company (two projects) | B | B |

## How to verify
- After confirming an order: `sale.order.order_line.project_id.company_id` and
  `sale.order.order_line.project_id.account_id.company_id` both equal `sale.order.company_id`.
- Before confirming: read `project_template_id` with the selling company active, then that template's `company_id`.

## Pitfalls
- Reading `project_template_id` with another company active returns nothing or another template, because it is
  `company_dependent`. Always check it with the selling company active.
- Correcting the project afterwards does not repair the account. Setting `company_id` on such a project left its account
  empty (measured): `_inverse_company_id` skips an account with no company. Set `company_id` on the account too.
- An empty company is not an obvious error: the order confirms and nothing warns. The project and account are then
  visible to every company: `project_comp_rule` and `analytic_comp_rule` (each module's `security/ir.access.csv`) allow
  an empty `company_id`.
- The rule depends on the number of projects on the order: adding a second templated line keeps the order's company,
  so a test with two lines does not prove the one-line case.
- A company on the template binds it to that company, so one shared template no longer serves several companies.

## Alternatives
- No template: the project takes the order's company, but no tasks or settings are copied.
- A global project on the product (`service_tracking` `task_global_project`, `project_id`, also `company_dependent`):
  the sale adds tasks to one existing project of that company instead of creating one per order.
