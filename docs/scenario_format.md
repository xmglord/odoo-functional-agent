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
| `as` | no | the test user every step acts as (see "Acting as a test user"); a step's own `as` overrides it |
| `users` | no | test users the scenario gives groups itself, only when the plan defines no role (see below) |

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

### Acting as a test user

`ofa_bot` holds every group the admin has, so it skips approvals and record rules: an order it confirms never waits
for a manager. To prove what a role can and cannot do, a step acts as a test user. `ofa provision` creates three,
`ofa_user_1` to `ofa_user_3`, internal users of the main company with only `base.group_user`, each with its own API
key next to the bot's.

- `as` on a step, or at the top level for every step, is a `{"$ref"}`, `{"$var"}` or `{"$search"}` naming one of
  them. That step's calls (create, search, write, call, read, assert) go with that user's key, so Odoo applies its
  access rights, record rules and approval limits. References are still resolved by the bot, and evidence is read by
  the bot. A step without `as` runs as the bot, for example the manager's approval.
- **The plan gives the role.** When the requirement defines roles (a buyer, a manager, a user per company), an
  `upsert_record` op of the plan adopts a test user and sets its `group_ids` and `company_ids` with `$set` (see
  "Test identities" in `plan_format.md`). The scenario then only says `"as": {"$ref": "__ofa__.<key>"}`. This way
  the author approves the role at the review stop, and the test proves the plan's configuration, not the scenario's
  assumption.
- **`users` only without a plan role.** `"users": {"<name>": {"login": "ofa_user_2", "groups": [refs],
  "companies": [refs]}}` gives that user exactly those groups (and companies, the first being its default) before
  the steps run, and `"as": "<name>"` acts as it. The report marks such a user "scenario users (assumption)".
  Declaring a user that a plan role owns is an `error` (`TEST_USER_HAS_ROLE`).
- A test user never gets an administrator group: `base.group_system` or `base.group_erp_manager`, or any group that
  implies one. `ofa` checks the requested groups (with what they imply) before writing and the user's
  `all_group_ids` after, and refuses with `ADMIN_GROUP_ON_TEST_USER`. In `users` that is an `error` at the reserved
  step `identities`.

`test.json` lists, per scenario, each test user a step acted as: its login, what set its groups (`plan role
__ofa__.<key>`, `scenario users (assumption)` or `provisioned, no role`) and its effective groups. `report.md`
shows them in an "Identities" table.

## Steps

Every step has `id` (`^[a-z0-9_]{1,80}$`, unique across preconditions and steps; `requires` is reserved), `action`
and `model`, and may have `company` (see Company context).

| Action | Required keys | Optional keys | JSON-2 call |
|---|---|---|---|
| `create` | `values` | `save_as`, `expect_error` | `create` with `vals_list=[values]`; `save_as` stores the new id |
| `write` | `target`, `values` | `expect_error` | `write` with `ids=[target...]`, `vals=values` |
| `call` | `target`, `method` | `params`, `wizards`, `expect_error` | the record method with `ids=[target...]` and `params` as named arguments, following wizards |
| `search` | `domain` | `limit`, `save_as`, `expect` (`count` only) | `search`; `save_as` stores the id list |
| `read` | `target`, `fields` | `save_as`, `expect`, `expect_error` | `read`; `save_as` stores the rows |
| `assert` | `target`, `expect` (with `fields`) | | `read` of the fields named in `expect.fields` |

`target` must resolve to one record id or a non-empty list of ids.

`call` follows wizard actions (a returned `ir.actions.act_window` with `target: "new"`). Two wizards are handled by
default: `confirm.stock.sms` → `dont_send_sms` and `stock.backorder.confirmation` → `process`. `wizards` adds or
overrides entries as `{wizard model: method}`. Any other wizard fails the step with `UNHANDLED_WIZARD`.

### Expecting a refusal

A negative test proves that Odoo refuses something: a billing clerk cannot post a manual entry, nobody can change a
closed month. Give that step `expect_error`:

```json
{"id": "s010", "action": "write", "model": "account.tax", "as": {"$ref": "__ofa__.role_clerk"},
 "target": {"$ref": "account.1_sale_tax_template"}, "values": {"amount": 10},
 "expect_error": {"class": "AccessError", "message_contains": "You are not allowed to modify 'Tax'"}}
```

- `class` is one of `AccessError`, `UserError`, `ValidationError`, `MissingError`, `RedirectWarning`. It must be the
  exact class Odoo raised (`odoo.exceptions.<class>`): `UserError` does not accept a `ValidationError`, although one
  is a subclass of the other.
- `message_contains` is required and must be part of Odoo's message. **Write it in English, copied from the Odoo
  source or from a run's `test.json`, never guessed.** Odoo translates messages to the acting user's language;
  `ofa_bot` and the test users are created with `lang` `en_US`, and `ofa apply` refuses to change it.
- Only on `create`, `write`, `call` and `read`, and not together with `expect` or `save_as`: a refused call leaves
  nothing to check or save.
- Before the call, `ofa` checks as the bot that every field the step names exists: the keys of `values` (and of
  `$create` lines one level down) and `fields`. Odoo checks access rights before field names, so a misspelled field
  in a refused write would otherwise come back as the expected `AccessError` and pass. An unknown field is an `error`.
  Method parameters of a `call` are not checked.

The step's status:

| What happens | Status |
|---|---|
| Odoo refuses with that class and the text is in its message | `pass` (message `refused as expected: ...`) |
| The call succeeds | `fail` |
| Odoo refuses with another business exception, or the same class with another text | `fail`: something refused it, but not the rule the test is about |
| Odoo raises something that is not a business exception (`builtins.ValueError` for a field that does not exist, a 422 for bad parameters) | `error`: the scenario is wrong |
| An `ofa` error (a reference that does not resolve, a guard refusal, the network) | `error` |

Each JSON-2 call is its own transaction, so a refused call leaves nothing behind. The scenario goes on after a
passing `expect_error` step: read back that nothing changed (the tax still at 15, no entry created), because the
refusal alone does not show that.

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

- `fail`: an expectation did not hold, Odoo refused a call (for example a `UserError`) that had no `expect_error`,
  or a reference did not resolve. The configuration does not support the flow. A step with `expect_error` follows
  its own table (see Expecting a refusal).
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
