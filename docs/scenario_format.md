# Scenario format `ofa.scenario/1`

A scenario is a JSON file that proves one business flow works on a demo database: it creates records, calls the
same buttons a user would press, and reads fields back to check the result. `ofa test` runs scenarios; reusable
ones live in `scenarios/20.0/<area>/`, plan-specific ones in `<plan_dir>/scenarios/`.

## Example

```json
{
  "format": "ofa.scenario/1",
  "id": "sales_quote_to_delivery",
  "area": "sales_crm",
  "odoo_version": "20.0",
  "edition": "community",
  "description": "A confirmed quotation creates one delivery.",
  "requires": {"modules": ["sale_management", "stock"]},
  "preconditions": [
    {"id": "p010", "action": "search", "model": "res.partner",
     "domain": [["id", "=", {"$ref": "base.res_partner_12"}]], "expect": {"count": 1}}
  ],
  "steps": [
    {"id": "s010", "action": "create", "model": "sale.order",
     "values": {"partner_id": {"$ref": "base.res_partner_12"},
                "order_line": {"$create": [{"product_id": {"$search": {"model": "product.product",
                                                                       "domain": [["default_code", "=", "FURN_0001"]]}},
                                            "product_uom_qty": 2}]}},
     "save_as": "so"},
    {"id": "s020", "action": "call", "model": "sale.order", "target": {"$var": "so"}, "method": "action_confirm"},
    {"id": "s030", "action": "search", "model": "stock.picking", "domain": [["sale_id", "=", {"$var": "so"}]],
     "save_as": "pickings", "expect": {"count": 1}},
    {"id": "s040", "action": "assert", "model": "sale.order", "target": {"$var": "so"},
     "expect": {"fields": {"state": {"eq": "sale"}, "amount_total": {"gt": 0}}}}
  ],
  "evidence": [{"label": "confirmed_order", "model": "sale.order", "target": {"$var": "so"},
                "fields": ["name", "state", "amount_total"], "screenshot": true}]
}
```

The partner and product identifiers show the syntax only. Check real identifiers with `ofa inspect` before using
them.

## Top-level keys

| Key | Required | Meaning |
|---|---|---|
| `format` | yes | always `ofa.scenario/1` |
| `id` | yes | `^[a-z0-9_]{1,80}$`, unique within one `ofa test` run |
| `area` | yes | `sales_crm`, `purchase_inventory`, `accounting`, `multi_company` or `l10n_mx` |
| `odoo_version` | yes | must equal the target's version, e.g. `20.0` |
| `edition` | yes | `community` or `enterprise`; an enterprise scenario on a community target is an `error` |
| `description` | yes | the business flow this proves |
| `requires.modules` | no | modules that must be installed; a missing one is an `error` |
| `preconditions` | no | steps run before `steps`; any failure there is an `error` |
| `steps` | yes | non-empty list of steps |
| `evidence` | no | records to read back and, optionally, screenshot |
| `company` | no | a `{"$ref"}`, `{"$var"}` or `{"$search"}` naming a `res.company`; every call of the scenario runs in that company (see below) |

Unknown keys are rejected, at the top level and in steps, so typos fail at load time instead of being ignored.

### Company context

`ofa_bot` belongs to every company the admin has, and without a context Odoo works in the bot's default company. To
see the database the way a user who picked another company sees it, name the company:

- top-level `company`: every precondition, step and evidence read runs with `allowed_company_ids: [<id>]` in the
  context, as `company` does for plan operations;
- `company` on a step or on an evidence item: overrides the scenario's for that step or read only.

Record rules then apply to that company: a record of another company is not found, and company-dependent values
(for example a customer's `total_due`) are computed for it. A wizard opened by a `call` step keeps the company and
adds the action's own context. A `company` that does not resolve to one id fails the step. Use it instead of
changing `ofa_bot`'s `company_ids`.

## Steps

Every step has `id` (`^[a-z0-9_]{1,80}$`, unique across preconditions and steps; `requires` is reserved), `action`
and `model`, and may have `company` (see Company context).

| Action | Required keys | Optional keys | JSON-2 call |
|---|---|---|---|
| `create` | `values` | `save_as` | `create` with `vals_list=[values]`; `save_as` stores the new id |
| `write` | `target`, `values` | | `write` with `ids=[target...]`, `vals=values` |
| `call` | `target`, `method` | `params`, `wizards` | the record method with `ids=[target...]` and `params` as named arguments, following wizards |
| `search` | `domain` | `limit`, `save_as`, `expect` (`count` only) | `search`; `save_as` stores the id list |
| `read` | `target`, `fields` | `save_as`, `expect` | `read`; `save_as` stores the rows |
| `assert` | `target`, `expect` (with `fields`) | | `read` of the fields named in `expect.fields` |

`target` must resolve to one record id or a non-empty list of ids.

`call` follows wizard actions (a returned `ir.actions.act_window` with `target: "new"`). Two wizards are handled by
default: `confirm.stock.sms` → `dont_send_sms` and `stock.backorder.confirmation` → `process`. `wizards` adds or
overrides entries as `{wizard model: method}`. Any other wizard fails the step with `UNHANDLED_WIZARD`.

## Value references

Any value (in `values`, `domain`, `params`, `target` and `expect`) may contain these one-key objects:

| Reference | Becomes |
|---|---|
| `{"$ref": "module.name"}` | the id of that external identifier; `__ofa__.<key>` is a record the plan created |
| `{"$var": "name"}` | a value saved earlier with `save_as` |
| `{"$search": {"model": m, "domain": [...]}}` | the single matching id; zero or several matches fail the step |
| `{"$set": [refs...]}` | `[[6, 0, ids]]` for an x2many field |
| `{"$add": [refs...]}` | `[[4, id], ...]` |
| `{"$create": [values...]}` | `[[0, 0, values], ...]`, e.g. order lines; allowed in scenarios, not in plans |

## Expectations

`expect` has `count` and/or `fields`:

- `count`: an integer (exact match) or an operator object such as `{"gte": 1, "lte": 3}`.
- `fields`: `{field: {operator: value}}`. Every operator must hold on every record read.

| Operator | Holds when the field value |
|---|---|
| `eq`, `ne` | equals / differs from the value |
| `in`, `not_in` | is / is not in the given list |
| `gt`, `gte`, `lt`, `lte` | compares as a number; an empty field (`false`) never holds |
| `contains` | contains the substring (text), or the id or every id of a list (x2many) |

Before comparing, a many2one read as `[id, name]` becomes `id` and an x2many id list is sorted, so
`{"eq": {"$ref": "base.mx"}}` works on a `country_id`.

A `$var` set by a `search` step holds a list of ids, even when the search found one record. To compare a many2one
with it, use `in` (or `not_in`): `{"lot_id": {"in": {"$var": "lot_early"}}}`. With `eq` the check fails, and the
message says so.

Assertions only read fields back. They never call helper methods: many public methods are not callable over RPC,
and a read-back check is what a user would see on screen.

## Status

Each step ends `pass`, `fail`, `error` or `skipped`; the scenario takes the first non-pass status.

- `fail`: an expectation did not hold, Odoo refused a call (for example a `UserError`), or a reference did not
  resolve. The configuration does not support the flow.
- `error`: the scenario could not be set up or the environment broke: a precondition failed, a required module is
  missing, the version or edition does not match, or the server is not answering.
- The first failing step stops the scenario. The remaining steps are reported as `skipped`.

`ofa test` exits 0 when every scenario passes, 1 when any fails, 4 when any is in error, and 2 when a file is not a
valid scenario (nothing is run then). The artifacts it writes are described in [run_artifacts.md](run_artifacts.md).

## Evidence

Each `evidence` item has a unique `label`, `model`, `target` and `fields`, plus optional `screenshot` and `company`. After the
steps, `ofa test` reads those fields back into `records.json`. With `screenshot: true`, the record's URL goes into
`screenshot_targets.json`. Evidence is collected for passing and failing scenarios, not for scenarios in error.
Use snake_case labels: they become part of the screenshot file name.
