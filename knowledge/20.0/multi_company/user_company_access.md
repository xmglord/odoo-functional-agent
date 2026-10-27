---
title: User access to companies (company_ids, allowed_company_ids, the ofa bot)
area: multi_company
odoo_version: 20.0
edition: community
source: [odoo/odoo/addons/base/models/res_users.py@20.0, odoo/odoo/orm/environments.py@20.0, odoo/odoo/addons/base/models/res_company.py@20.0, odoo/addons/rpc/controllers/json2.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [base]
models: [res.users, res.company]
settings: []
---

## When to use
- If a person works for several companies of the group (a shared accountant, the group's purchasing team), give
  them every such company in `company_ids` and pick their default in `company_id`.
- If a person must only see one company's data (a store clerk, a subsidiary's salesperson), give them that company
  only: the record rules then hide every record restricted to the other companies.
- When a plan creates companies, decide which existing users need them; Odoo only grants them to the user who
  created them.

## Configuration
- `res.users.company_ids` (many2many, "Companies"): the companies the user may work in.
- `res.users.company_id` (many2one, required, "Company"): the default company; it must be in `company_ids`
  (constraint `_check_user_company`, `ValidationError` "Company ... is not in the allowed companies for user ...").
- `base.group_multi_company` ("Multi Companies"): Odoo adds it to a user automatically when `company_ids` has more
  than one company and removes it at one (`res_users.py`, create/write). It shows the company switcher. Do not set it
  by hand.
- Active companies per request: the `allowed_company_ids` context key (what the company switcher sends). It must be
  a subset of the user's companies, otherwise `AccessError` "Access to unauthorized or invalid companies."
  `env.company` is its first id, `env.companies` all of them.
  - **Without `allowed_company_ids`** (a plain RPC call, a JSON-2 call without `context`), `env.companies` is
    **every** company of the user (`environments.py`, `companies`). Such a caller sees the records of all its
    companies at once.
- The record rules evaluate `company_ids` = `env.companies` (see
  [shared_vs_company_records.md](shared_vs_company_records.md)).
- In a plan: an op's `company` key (`{"$ref": ...}`) sends `allowed_company_ids: [<id>]` with every call of that op,
  so it reads and writes as if only that company were active (settings, company-dependent fields, default taxes).
  Scenario steps have no such key: they run with the bot's full company list.

## How to verify
- `res.users` read `company_ids` and `company_id` of the user.
- `base.group_multi_company` in `all_group_ids` when the user has more than one company.
- Behaviour: as a user without company B, `search` `[["id", "=", <record of B>]]` is empty (scenario
  `multi_company_isolation`).

## Pitfalls
- **New companies are granted only to their creator and the superuser.** `res.company.create` links
  `self.env.user` and the superuser and nobody else. Live: after `ofa apply` created two companies, `ofa_bot` had
  them and `admin` did not, so the admin does not see them in the web client until someone adds them to the admin's
  `company_ids`. A company created in the UI by the admin is likewise not given to `ofa_bot`: `ofa apply` adds every
  company a plan creates to the bot, but not companies created some other way.
- **The ofa bot sees every company it has.** `ofa_bot` is provisioned with the admin's `company_ids` (on the demo
  template: the five demo companies) plus every company a plan creates. A scenario call without a company carries
  no `allowed_company_ids`, so a search finds records of all those companies. To check what a user of one company
  sees, give the scenario or the step a `company` key (`docs/scenario_format.md`), as `multi_company_isolation`
  does; never change the bot's `company_ids` for it.
- `allowed_company_ids` with a company the user lacks fails the whole call with `AccessError`; in a plan, the op's
  `company` must be a company the bot has (a company created earlier in the same plan is).
- Removing a company from a user does not touch the records of that company; it only hides them. Removing the
  user's default `company_id` from `company_ids` fails the constraint.
- The user's companies are cached (`_get_company_ids`, `ormcache`); a write on `company_id`/`company_ids`
  invalidates the access cache, and live the change applied from the next call on.

## Alternatives
- Restrict by access groups (sales only, purchase only) instead of companies when the split is by job, not by legal
  entity.
- Branches when a unit should see the parent's master data but not its documents (see
  [companies_and_branches.md](companies_and_branches.md)).
