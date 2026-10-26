---
title: Leads, opportunities and pipeline stages
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/crm/acquire_leads/convert.html, https://www.odoo.com/documentation/20.0/applications/sales/crm/pipeline/lost_opportunities.html, odoo/addons/crm/models/crm_lead.py@20.0, odoo/addons/crm/models/crm_stage.py@20.0, odoo/addons/crm/models/res_config_settings.py@20.0, odoo/addons/crm/data/crm_stage_data.xml@20.0, odoo/addons/crm/views/crm_lead_views.xml@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [crm]
models: [crm.lead, crm.stage, crm.lost.reason, crm.lead.lost, res.config.settings]
settings: [group_use_lead]
---

## When to use
- If the business receives many unqualified requests (web forms, emails, fairs) and wants someone to qualify them
  before a salesperson spends time on them, enable **Leads** (`group_use_lead`), because without it every new
  `crm.lead` is created directly as an opportunity in the pipeline.
- If every request is already a real sales opportunity (small B2B team, inbound calls only), leave Leads off: one
  record type and one pipeline is less work.
- If the sales process has distinct steps the business wants to measure (qualified, proposal sent, negotiation),
  model them as `crm.stage` records, because reports and the kanban pipeline group by `stage_id`.
- If different teams sell differently, restrict stages to teams with `crm.stage.team_ids` instead of one shared list.

## Configuration
- Leads and opportunities are one model, `crm.lead`, told apart by `type` (selection `lead` / `opportunity`). The
  default `type` is `lead` only when the user has `crm.group_use_lead`; otherwise `opportunity`
  (`odoo/addons/crm/models/crm_lead.py@20.0`).
- Setting: `res.config.settings.group_use_lead` (label "Leads", implies `crm.group_use_lead`). Being a `group_*`
  settings field, saving it adds `crm.group_use_lead` to the implied groups of `base.group_user`
  (`odoo/odoo/addons/base/models/res_config.py@20.0`). Per team, `crm.team.use_leads` also has to be on for that
  team's incoming records to start as leads (see the sales teams entry).
- Conversion: the form button "Convert to Opportunity" calls `crm.lead.action_convert_to_opportunity` (no
  parameters). It writes `type = 'opportunity'`, `date_conversion`, a stage if the lead has none, and links or
  creates the customer (`partner_id`). For many leads at once there is the wizard `crm.lead2opportunity.partner.mass`
  (`action_apply`).
- Stages: `crm.stage` with `name`, `sequence`, `is_won`, `fold`, `team_ids`, `requirements`,
  `rotting_threshold_days`. Default data: `crm.stage_lead1` New, `crm.stage_lead2` Qualified, `crm.stage_lead3`
  Proposition, `crm.stage_lead4` Won (`is_won = True`) (`odoo/addons/crm/data/crm_stage_data.xml@20.0`).
- Won and lost: `action_set_won` moves the record to the next `is_won` stage and sets `probability = 100`.
  `action_set_lost` archives it (`active = False`) and sets `probability = 0`; the "Lost" button opens the wizard
  `crm.lead.lost` (`lost_reason_id`, `lost_feedback`, method `action_lost_reason_apply`). Lost reasons are
  `crm.lost.reason` records.
- `won_status` (selection `won` / `lost` / `pending`, stored, computed): `won` when `probability == 100` and the stage
  is `is_won`; `lost` when inactive with `probability == 0`; otherwise `pending`.

## How to verify
- Setting: `base.group_user` (`res.groups`) has `crm.group_use_lead` in `implied_ids`.
- Conversion: on the `crm.lead`, `type == 'opportunity'`, `date_conversion` is set, `partner_id` is set, `stage_id`
  is set.
- Won: `won_status == 'won'`, `probability == 100`, `stage_id.is_won` true (read the stage record).
- Lost: `active == False`, `probability == 0`, `won_status == 'lost'`, `lost_reason_id` set if a reason was given.
  Search lost records with `active` in the domain (`[["active","=",False]]`), or they are filtered out.
- Stages: read `crm.stage` `name`, `sequence`, `is_won`, `team_ids`.

## Pitfalls
- No single-lead conversion wizard in 20.0 source. Older versions (and the 20.0 docs page) describe a conversion
  dialog with "Conversion Action" and "Customer" choices (model `crm.lead2opportunity.partner`); that model is not in
  `odoo/addons/crm/wizard/` @20.0. The button calls `action_convert_to_opportunity` directly; only the mass wizard
  remains.
- `convert_opportunity(partner, user_ids, team_id)` takes a `res.partner` recordset as `partner`, so it cannot be
  called over JSON-2 with an integer id. Set `partner_id` on the lead first, then call
  `action_convert_to_opportunity`.
- Conversion skips leads that are inactive or already won.
- Lost opportunities are archived, so searches without `active` in the domain miss them.
- The won stage is found by sequence relative to the current stage; a pipeline with several `is_won` stages can move
  a record to an unexpected one.
- Enabling Leads does not convert existing records; existing opportunities stay opportunities.

## Alternatives
- Without Leads, qualify inside the pipeline with an early stage ("New") and a lost reason for disqualified ones.
- Use tags (`crm.tag`, `tag_ids`) or lead properties (`lead_properties`, defined per team) for classification that
  is not a process step.
- For automatic scoring instead of manual qualification, predictive lead scoring settings
  (`predictive_lead_scoring_fields`, `predictive_lead_scoring_start_date`) fill `automated_probability`.
