---
title: Lock dates (closing periods)
area: accounting
odoo_version: 20.0
edition: community
source: [odoo/addons/account/models/company.py@20.0, odoo/addons/account/models/account_move.py@20.0, odoo/addons/account/models/account_lock_exception.py@20.0, enterprise/account_accountant/wizard/account_change_lock_date.py@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [account, account_accountant]
models: [res.company, account.move, account.lock_exception, account.change.lock.date]
settings: []
---

## When to use
- If a month or year has been closed (VAT return filed, statements sent to the auditor), lock it so nobody adds or
  changes entries in it. Use the lock that matches what was closed:
  - `sale_lock_date` / `purchase_lock_date`: sales or purchase journals only (invoicing team done for the month);
  - `tax_lock_date`: entries with taxes (tax return filed);
  - `fiscalyear_lock_date` ("Global Lock Date"): every journal (period closed);
  - `hard_lock_date`: irreversible, no exceptions (legal requirement for an inalterable close).
- If one person must still post into a locked period (an auditor's adjustment), grant a temporary **exception**
  instead of moving the lock date back.

## Configuration
- Fields on `res.company`: `fiscalyear_lock_date`, `tax_lock_date`, `sale_lock_date`, `purchase_lock_date`,
  `hard_lock_date` (dates; an entry dated on or before the date is affected). There are **no** `res.config.settings`
  fields for them (checked live: no settings field name contains `lock_date` apart from purchase's `lock_confirmed_po`
  / `po_lock`). A plan sets them with an `upsert_record` on the company (key the company, `values` with the dates).
- Per-user view: computed `user_fiscalyear_lock_date`, `user_tax_lock_date`, `user_sale_lock_date`,
  `user_purchase_lock_date`, `user_hard_lock_date` give the effective date for the current user after exceptions
  (and including parent companies).
- Exceptions: `account.lock_exception` with `company_id`, `user_id` (empty = everyone), `lock_date_field`
  (`fiscalyear_lock_date`, `tax_lock_date`, `sale_lock_date`, `purchase_lock_date`; never the hard lock),
  `lock_date` (the date the lock is lowered to for this exception), `end_datetime` (empty = forever), `reason`,
  computed `state` (`active`, `revoked`, `expired`).
- UI wizard (Enterprise `account_accountant`): `account.change.lock.date` with the same lock fields plus
  `exception_applies_to` (`me`, `everyone`), `exception_duration` (`5min`, `15min`, `1h`, `24h`, `forever`),
  `exception_reason`, confirmed by `change_lock_date`.

## How to verify
- Read the lock fields on `res.company`.
- For a given user: read `user_*_lock_date` on the company as that user.
- Exception: `account.lock_exception` search `[["company_id", "=", <id>], ["lock_date_field", "=", "<field>"]]`,
  `state == 'active'`.
- Behaviour (scenario): post an invoice dated inside the locked period and read its `account.move.date`: it is moved
  to the first open period (see Pitfalls), while `invoice_date` keeps the original date.

## Pitfalls
- **20.0 postpones instead of refusing.** Posting a document dated inside a locked period does not fail: `_post`
  replaces `account.move.date` with the date returned by `_get_accounting_date` (after the latest violated lock
  date; for sales documents the end of that month or year, capped at today). The field help says so ("will be
  postponed to a later time"). Modifying or deleting entries already posted in the locked period still raises
  `UserError` ("You cannot add/modify entries prior to and inclusive of: ...", `_check_fiscal_lock_dates`).
- The hard lock date can only move forward ("A new Hard Lock Date must be posterior (or equal) to the previous
  one.") and cannot be removed ("The Hard Lock Date cannot be removed."), and setting it fails while draft entries
  exist on or before it (`_validate_locks`). Never set it on a demo DB you want to reuse.
- Setting `fiscalyear_lock_date` (or the hard lock) fails while unreconciled bank statement lines exist on or before
  that date (`RedirectWarning` "There are still unreconciled bank transactions in the period you want to lock.").
- Writing a soft lock date revokes the active exceptions for that lock and recreates them with the new date
  (`res.company.write`).
- Lock dates of a parent company also apply to its branches (`_get_user_lock_date` walks `parent_ids`).

## Alternatives
- Journal hashing (`account.journal.restrict_mode_hash_table`) to make posted entries tamper-evident without
  locking a period.
- Restricting who can post (accounting groups such as `account.group_account_manager` vs
  `account.group_account_invoice`) instead of lock dates, when the concern is people, not periods.

## Mexico notes
`l10n_mx_edi` (Enterprise) respects lock dates: when the SAT state of a CFDI changes (for example a cancellation)
it runs `_check_fiscal_lock_dates` and `_check_tax_lock_date` on the move, and the CFDI download from the SAT starts
after the latest lock date (`enterprise/l10n_mx_edi/models/account_move.py@20.0`,
`enterprise/l10n_mx_edi/models/res_company.py@20.0`). So locking a period also blocks CFDI changes that would touch
it. See the `l10n_mx` area.
