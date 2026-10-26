---
title: Sales teams and team membership
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/crm/pipeline/manage_sales_teams.html, odoo/addons/sales_team/models/crm_team.py@20.0, odoo/addons/sales_team/models/crm_team_member.py@20.0, odoo/addons/crm/models/crm_team.py@20.0, odoo/addons/crm/models/crm_team_member.py@20.0, odoo/addons/crm/models/res_config_settings.py@20.0, odoo/addons/sale/models/sale_order.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [sales_team, crm, sale]
models: [crm.team, crm.team.member, crm.stage, res.config.settings]
settings: [is_membership_multi, crm_use_auto_assignment, crm_auto_assignment_action]
---

## When to use
- If the business has groups of salespeople with their own targets, pipeline or manager (regions, product lines,
  channels), create one `crm.team` per group, because opportunities and sales orders carry `team_id` and every
  sales report can be grouped by it.
- If one salesperson works for several teams, enable **Multi Teams** (`is_membership_multi`), because otherwise a
  user can be an active member of a single team only.
- If leads should be distributed to salespeople by rules (country, size, capacity) instead of by hand, enable
  **Rule-Based Assignment** (`crm_use_auto_assignment`) and set per-member domains and capacities.
- If a team should qualify incoming requests before they reach the pipeline, turn on `use_leads` on that team (needs
  the Leads setting, see the leads and pipeline entry).

## Configuration
- `crm.team` (module `sales_team`): `name`, `user_id` (Team Leader), `company_id`, `sequence`, `active`,
  `member_ids` (computed from memberships, writable), `crm_team_member_ids` (one2many to `crm.team.member`).
- CRM adds on `crm.team`: `use_leads` ("Leads"), `use_opportunities` ("Pipeline", default true), `alias_id` /
  `alias_full_name` (email alias that creates leads for the team), `assignment_optout`, `assignment_domain`,
  `lead_properties_definition` (custom lead fields per team) (`odoo/addons/crm/models/crm_team.py@20.0`).
- `crm.team.member`: `crm_team_id`, `user_id`, `active`; CRM adds `assignment_domain`,
  `assignment_domain_preferred`, `assignment_max` ("Average Leads Capacity (on 30 days)") and `lead_month_count`.
- Settings (`res.config.settings`, crm module):
  - `is_membership_multi` ("Multi Teams"), stored in `ir.config_parameter` key `sales_team.membership_multi`.
  - `crm_use_auto_assignment` ("Rule-Based Assignment"), key `crm.lead.auto.assignment`.
  - `crm_auto_assignment_action` (`manual` / `auto`), with `crm_auto_assignment_interval_type` and
    `crm_auto_assignment_interval_number`; `auto` activates the assignment cron.
- Stages can be limited to teams with `crm.stage.team_ids`; a stage with no team is shared by all teams.
- Default team on documents: `sale.order.team_id` and `crm.lead.team_id` are computed from the salesperson
  (`user_id`) through `crm.team._get_default_team_id`: first a team the user is a member or leader of, then any team
  of the company. Demo/default team: `sales_team.team_sales_department`.

## How to verify
- Team exists: `crm.team` record with the expected `name`, `user_id`, `use_leads`, `use_opportunities`.
- Membership: `crm.team.member` records with `crm_team_id` = the team and `user_id` = each salesperson, `active`
  true; or read `member_ids` on the team.
- Multi Teams: the team's computed `is_membership_multi` reads true (it reads the boolean parameter
  `sales_team.membership_multi`, which settings store with the typed `set_bool`; read the parameter itself with
  `get_bool`, not `get_param`, which no longer exists in 20.0).
- Default team works: create a `sale.order` with `user_id` = a member and read back `team_id`.

## Pitfalls
- Without Multi Teams, adding a user to a second team archives or blocks the first membership (`member_warning`
  explains it); scripted plans that add the same user to two teams fail or silently move them.
- `team_id` on orders and leads is computed from `user_id`; writing a team and then changing the salesperson can
  recompute it.
- The 20.0 docs mention an "Invoicing Target" field on the team; no `invoiced_target` field exists in the 20.0
  `sale`, `sales_team`, `crm` or Enterprise source, so do not plan it.
- The docs describe member capacity per day; the field label in source is "Average Leads Capacity (on 30 days)".
- An email alias needs a working incoming mail setup to create leads; on a demo database it only proves the
  configuration, not delivery.

## Alternatives
- For simple territory splitting without teams, use tags or salesperson filters on reports.
- For commission or target tracking, the settings field `module_sale_commission` installs the commission module
  instead of modelling targets on the team.
