# Multi-company (20.0)

Several companies in one database: when a unit is its own company or a branch, which records every company shares
and which belong to one, how users get access to companies, which settings are per company, the Enterprise
inter-company rules that mirror orders and invoices, and what group reporting covers. Company-specific accounting
(charts, taxes, lock dates) is in the accounting area; Mexican companies are in the `l10n_mx` area.

Start with the companies entry: whether a unit is a company or a branch decides what it shares, and it cannot be
changed afterwards.

| Entry | Use it when the requirement mentions |
|---|---|
| [Companies vs branches (company hierarchy)](companies_and_branches.md) | a holding, subsidiaries, a new company, branches, offices or stores of one legal entity |
| [Shared vs company-specific records](shared_vs_company_records.md) | products or contacts shared by the group, records private to one company, "incompatible companies" errors, per-company prices or fiscal positions on a shared record |
| [User access to companies](user_company_access.md) | users who work for several companies, users restricted to one company, the company switcher |
| [Per-company vs global settings](per_company_settings.md) | a setting only one company should use, settings in a multi-company database |
| [Company of a project created from a sale](project_template_company.md) | project templates on service products, projects or analytic accounts created by a sale with no company |
| [Inter-company rules](intercompany_rules.md) | companies that buy from and sell to each other, mirror sales/purchase orders, inter-company invoices and bills |
| [Multi-company reporting and consolidation](multi_company_reporting.md) | group balance sheet or P&L, consolidation, VAT groups (tax units), inter-company balances |

Scenarios for this area live in `scenarios/20.0/multi_company/`. Both need the fixture plan in
`scenarios/20.0/multi_company/setup/` applied first (Enterprise: it installs the inter-company modules).

- `multi_company_isolation` (community): working in the main company, a contact, product and sales order of the
  subsidiary are invisible; working in its branch, the contact and product are visible and the order is not;
  working in the subsidiary, the order is visible. `ofa_bot` is a member of every company (the admin's five demo
  companies from provisioning, plus every company a plan creates), so each check names its company with the
  step's `company` key, which sends `allowed_company_ids` like the company switcher does. The bot's own
  `company_ids` are never changed.
- `multi_company_intercompany_so_po` (enterprise): a purchase order of the main company to the subsidiary creates
  the subsidiary's draft sales order (`sale_purchase_inter_company_rules`).

Not covered by a scenario: inter-company invoices to bills, sales orders to purchase orders, and report output
(reports are read in the UI). There is no consolidation module in 20.0, so formal consolidation is not covered.

## Upkeep log

| Entry | Agent time: tokens | Agent time: minutes |
|---|---|---|
| companies_and_branches.md | 3,043 | 0.4 |
| shared_vs_company_records.md | 5,759 | 0.7 |
| user_company_access.md | 3,734 | 0.5 |
| per_company_settings.md | 3,566 | 0.5 |
| intercompany_rules.md | 6,394 | 0.7 |
| multi_company_reporting.md | 2,815 | 0.4 |
| project_template_company.md | not measured | not measured |
| overhead | 284,189 | 19.5 |

Agent time is measured from the authoring agent's session transcript, between markers it printed before and after each
entry. Two entries were edited again after their end markers inside new marker pairs: `companies_and_branches.md` (a
cross-reference in Mexico notes) and `shared_vs_company_records.md` (twice: a stray lint comment removed, and the
product default taxes corrected after reading `_force_default_tax`). Tokens are the new tokens of its API calls in that
window (input, cache writes and output); re-reads of already cached context are excluded (18.7 M such tokens over the
session, 98% of the raw total). The agent researched all topics before the first marker, so the per-entry windows cover
writing only and the research is in overhead; compare areas by their totals, not per entry. The
`companies_and_branches.md` re-edit was a single call whose end marker did not parse, so its tokens are in overhead.
Overhead is the shared research plus the index, the fixture plan and the scenarios.
