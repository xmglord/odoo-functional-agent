# plan.md template

Copy the block below into `plans/<slug>/plan.md` and fill it in. One "Decision" section per business decision; a
decision may cover several ops. Rules:

- Every op id in plan.json appears at least once as the literal `[op_id]`, each id in its own brackets:
  `[op_010_install_sales] [op_020_discounts]`, never `[op_010_install_sales, op_020_discounts]`. `ofa validate`
  checks this.
- Write for a developer who is new to functional Odoo: the business problem first, then what Odoo does about it.
- Use exact technical names (module, model, field, settings field, group, xmlid) next to the business terms.
- Sources are compendium entries (`knowledge/20.0/<area>/<topic>.md`). When none covers a decision, write
  "Uncited: no compendium entry" and name the `ofa inspect` check that confirmed the technical names.

```markdown
# <Plan title, same as plan.json "title">

- Requirement: [requirement.md](requirement.md)
- Target edition: community | enterprise
- Areas: sales_crm, ...

## Summary
Two to four sentences: what the business needs and the shape of the configuration that answers it.

## Decision 1: <short name>
- Ops: [op_010_...] [op_020_...]
- Decision: what gets configured, in one or two sentences.
- Business reason: which part of the requirement this answers, and why this is the right fit.
- What Odoo does:
  - models and fields: `sale.order.line.discount`, ...
  - settings: `group_discount_per_so_line` (res.config.settings), ...
  - menu path, for orientation only: Sales > Configuration > Settings > Pricing > Discounts
- Pre-state: already true in the template? (checked with `ofa inspect`; an op that is already satisfied reports
  `unchanged` on the first apply and proves nothing)
- Alternatives: other ways to reach the same result, and when to pick each instead.
- Pitfalls: what goes wrong with this setting, and how it shows up.
- Sources: `knowledge/20.0/<area>/<topic>.md` (or "Uncited: no compendium entry; names checked with
  `ofa inspect --target <slug> <model> --fields ...`")

## Decision 2: <short name>
...

## Not covered by this plan
Configuration the requirement needs that `ofa` cannot apply (UI-only steps, with menu paths), and anything
deliberately left out, with the reason. Write "Nothing." when empty.

## Glossary
- **<Functional term>**: one-line definition in business terms, plus the Odoo object it maps to.
```
