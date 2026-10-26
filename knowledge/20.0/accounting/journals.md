---
title: Journals (sales, purchase, bank, cash, miscellaneous)
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/account_journal.py@20.0, odoo/addons/account/models/account_payment_method.py@20.0, odoo/addons/account/models/account_payment.py@20.0, odoo/addons/account/models/account_move.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account]
models: [account.journal, account.journal.group, account.payment.method.line, account.move]
settings: []
---

## When to use
- Every journal entry belongs to a journal; the journal decides the **numbering** (its `code` is the sequence
  prefix), the **default account** and which documents can use it. The chart template creates one of each kind;
  add journals only when the business needs separate numbering or separate money accounts.
- If the company has several bank accounts, create one `bank` journal per account, because each bank journal has its
  own liquidity account, statements and reconciliation.
- If invoices of a business line or a branch need their own numbering (e.g. "EXP/2026/0001" for exports), create an
  extra `sale` journal and pick it on those invoices.
- If credit notes must have their own numbering, set `refund_sequence` on the sale/purchase journal.
- If posted entries must be tamper-evident (legal requirement in some countries), set `restrict_mode_hash_table`.

## Configuration
- `account.journal`: `name`, `code` (sequence prefix, unique per company: "Journal codes must be unique per
  company."), `type` (`sale`, `purchase`, `cash`, `bank`, `credit` = credit card, `general` = miscellaneous),
  `company_id` (required, read-only after creation), `active`, `sequence` (dashboard order), `currency_id` (only for
  journals in a foreign currency), `default_account_id`, `suspense_account_id` (bank/cash/credit),
  `profit_account_id` / `loss_account_id` (cash differences), `refund_sequence`, `payment_sequence`,
  `restrict_mode_hash_table`, `invoice_reference_type` (`partner`, `invoice`), `invoice_reference_model` (`odoo`,
  `euro`, `number`), `bank_account_id`, `journal_group_id` (`account.journal.group`, "Ledger group", used to filter
  reports).
- Payment methods of bank/cash journals: `inbound_payment_method_line_ids` / `outbound_payment_method_line_ids`
  (`account.payment.method.line`: `name`, `payment_method_id`, `code`, `payment_type`, `journal_id`,
  `payment_account_id` = the outstanding account payments with this method post to).
- Defaults filled on create (`_fill_missing_values`): a `bank`/`cash` journal without `default_account_id` gets a new
  liquidity account (code from `res.company.bank_account_code_prefix` / `cash_account_code_prefix`, xmlid
  `account.<company_id>_<type>_journal_default_account_<id>`), and `profit_account_id` / `loss_account_id` from the
  company's cash difference accounts; `sale` / `purchase` journals get the product category's income / expense
  account as `default_account_id`.

## How to verify
- Journal exists with the expected `type`, `code`, `company_id` and `default_account_id`.
- For bank journals: each `inbound_payment_method_line_ids` / `outbound_payment_method_line_ids` record has the
  expected `payment_account_id` (or none, see Pitfalls).
- A posted invoice in that journal: `account.move.journal_id` and a `name` starting with the journal `code`.

## Pitfalls
- **Outstanding accounts are empty by default on the generic chart.** On the live template DB every payment method
  line of company 1's bank journal (`account.1_bank`) has `payment_account_id = False`; only some localizations set
  them (`_assign_outstanding_account_to_payment_method_lines`, used by e.g. `l10n_in`, `l10n_ma`). What that means
  for payments depends on whether the full Accounting app is installed; see the payments entry.
- `restrict_mode_hash_table` cannot be unticked once hashed entries exist ("You cannot modify the field ... of a
  journal that already has accounting entries.").
- Template journal xmlids carry the company id (`account.1_sale`, `account.1_purchase`, `account.1_bank`,
  `account.1_general`, `account.1_exch` on the live template DB); look journals up by `company_id` and `type` (or
  `code`) for companies a plan creates.
- A purchase document can only use a `purchase` journal (`ValidationError` "Cannot create a purchase document in a
  non purchase journal", `account_move.py@20.0`, `_check_journal_move_type`).
- A journal with `currency_id` only takes entries in that currency; leave it empty for journals in the company
  currency.

## Alternatives
- One sale journal with analytic accounts, instead of extra journals, when the business only wants reporting per
  line of business, not separate numbering.
- Sequence editing (`document_sequence_editable` setting) for one-off numbering changes rather than a new journal.

## Mexico notes
Mexican invoices are numbered by journal like everywhere else. How the CFDI series and folio relate to the journal
`code` and the document name was not checked for this entry; see the `l10n_mx` area before adding journals for a
Mexican company.
