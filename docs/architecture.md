# Architecture

Five decisions shape the tool. Each is summarized here as context, decision and consequences, as they stand in the
code.

## 1. Execution channel: the JSON-2 API, the browser only for screenshots

**Context.** An agent can change Odoo through its HTTP API or by driving the web client. Driving the UI is slow,
brittle and hard to make repeatable; some configuration is reachable only in the UI.

**Decision.** Every write and every test read goes through Odoo 20's JSON-2 API, issued only by `ofa`. The browser
(Firefox DevTools MCP) is used after the tests pass, only to screenshot records on the loopback server; it never
writes.

**Consequences.** One HTTP client serves apply and test, and assertions run on data, not on pixels. Configuration
that only the UI can do cannot be applied; the skill must say so in plan.md and in the report, with the menu path.
Screenshots are best effort: when the browser is unavailable, the evidence is the records read back.

## 2. A deterministic executor and a reviewable plan format

**Context.** A language model is good at deciding what to configure and poor at doing it the same way twice.

**Decision.** One standard-library Python CLI, `ofa`, is the only component that touches Odoo. The model writes
only files: a plan (`plan.json`, four operation types with a rationale each, and `plan.md` explaining them) and
scenarios. The approved plan is frozen by its hash; `ofa apply` runs only that. Records a plan creates are keyed by
external ids in a private `__ofa__` namespace, so a re-apply finds them and reports `unchanged`.

**Consequences.** One place to guard, test and debug, and plans diff cleanly in review. Repeatability is defined as
"the same frozen plan on a fresh database gives the same state", checked with `ofa dump`; the same requirement text
does not give the same plan. Changing the plan format later means converting the published examples.

## 3. A guard in layers around demo databases

**Context.** The machine can host other Odoo databases on the same Postgres server, and the agent runs shell
commands.

**Decision.** Layer a sits in the `ofa` client constructor, so no subcommand can skip it: the target must be
registered by `ofa provision`, named `ofa_demo_*`, on loopback, and carry the marker UUID recorded at provisioning.
Only `provision` creates API keys. Layer b is a PreToolUse hook shipped with the plugin, active only once a session uses the agent, that denies shell commands
reaching Odoo or Postgres outside `ofa`, and browser navigation off loopback. The Odoo server config is hardened
(`list_db`, `dbfilter`, no cron threads), and `ofa server start` refuses one that is not.

**Consequences.** A database `ofa` did not create fails the marker check even if registered by hand. The hook is
pattern matching and has documented gaps ([guard.md](guard.md#known-gaps)). Claude Code's permission mode is not a
layer.

## 4. Demo databases cloned from a template

**Context.** Tests need fresh databases often, and installing Odoo modules takes minutes.

**Decision.** `ofa template build` creates one template database per Odoo version and edition, with demo data and a
fixed module list, against the user's own Odoo checkout and Postgres. `ofa provision <name>` clones it into
`ofa_demo_<name>`, copies the filestore, writes the marker, and creates the `ofa` bot user and three test users with
their API keys. `ofa drop` and `ofa reset` act only on registered demo names.

**Consequences.** A fresh database takes seconds. Demo databases share Postgres with the user's other databases,
which is why the guard's name and marker checks exist. Readers bring their own Odoo; what the template contains
(for example a localization module) also shapes what a test can hit.

## 5. A plain-file knowledge compendium

**Context.** The model's memory of Odoo is mixed across versions, and 20.0 renamed many models and fields.

**Decision.** The compendium lives in `knowledge/<version>/<area>/*.md`, one topic per file, with an index per
version and per area. Each entry has front matter (`odoo_version`, `edition`, `source` paths or URLs,
`verified_on`), decision rules ("if the business does X, configure Y because Z"), the models and settings involved,
and pitfalls. The skill reads it through the index and grep; there is no vector store. `ofa lint-plan` checks every
name a plan uses against the target and the 20.0 source.

**Consequences.** Readable without a running Odoo, and its upkeep is visible
([knowledge_upkeep.md](knowledge_upkeep.md)). Each new Odoo version copies the tree and re-verifies it.
