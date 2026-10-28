# Example 4: Mexican localization, CFDI-ready company

A fictional Mexican distributor of industrial supplies, Casa Albar, wants every fiscal document issued and stamped
from Odoo 20 (CFDI 4.0 invoices, payment receipts, credit notes, cancellations with substitution, fee bills with
withholdings) and the monthly SAT electronic accounting files produced there. The author wrote the requirement
([requirement.md](requirement.md)) and ran the `odoo-functional` skill on it in one interactive Claude Code session
(2026-10-28, 16:25 to 16:58 UTC) on a fresh demo database `t26`. The demo company `base.demo_company_mx` (company 4,
with the SAT's test RFC and a demo CSD) stands in for Casa Albar, as the requirement asks ("use that company as it
is").

**Stamping branch: STAMPS.** Every CFDI in the runs below was really stamped, and the cancellations really sent,
against the **test environment of a third-party PAC** (Quadrum), over the internet, on 2026-10-28. A re-run needs
internet access and depends on that test service being up. **The demo CSDs expire on 2027-05-18 (company 4, used here)
and 2027-01-18 (company 5)**, as shipped in the `l10n_mx_edi` 20.0 demo data (read on 2026-10-26); after that date a
re-run of this example stops stamping because of the certificate, not because of the configuration.

What to look at, in order:

1. [requirement.md](requirement.md): six numbered needs.
2. [plan.md](plan.md): the decisions, the **Test plan** and "Not covered", as finally approved.
3. [plan.json](plan.json): the 12 operations; [plan.approved](plan.approved) holds the hash of the approved version.
4. [scenarios/](scenarios/): the ten functional tests the skill wrote, in their final form.
5. The runs below, each with a `report.md`.

## What changed in the skill and in `ofa` since example 3

Used in this session:

- **`expect_error`** (`a54b6c3`, `2aa514c`): `t26_fiscal_data_guard` checks that posting an invoice with
  incomplete fiscal data is refused, with the exact class and message, then that the invoice stays a draft.
- **Rerun a fixed scenario in full** (`ab17e7f`): after fixing its own scenario mistakes the skill reran them in
  full.
- **Screenshot procedure** (`b61537e`): the skill logged out at the end, but the step as written then used
  `.click()` in a page script, which the plugin's guard refuses; the skill clicked through the menu instead. The
  step is corrected (`38dc7ac`).

Added after this session, because of what it showed, and used only by the maintainer re-run:

- **`save_as` on `call` and the `check` step** (`d604db7`). In the session a `call` step dropped what the method
  returned, so the SAT XML files could be generated but not read, and the trial balance could not be generated at
  all (`builtins.KeyError: column_groups`: its options must come from `get_options`, and a scenario could not pass
  one call's result to the next). Now a scenario can save the report's options and the exported file and assert on
  the XML.

## Runs

| Run | Who | What happened |
|---|---|---|
| [`20261028T163801Z_t26`](runs/20261028T163801Z_t26/report.md) | the skill, first approved plan | Apply of plan v1 (11 ops: 5 `created`, 5 `adopted`, 1 `unchanged` with `pre_state`: `l10n_mx_reports` was already in the template). Tests found two real defects: the general-public customer named "Publico en General" made the PAC reject the invoice as a global invoice without its node (CFDI40130), and an account the `l10n_mx` template creates with an invalid SAT code (`171.16000`). The automatic cancellation failed with the test PAC's `Code : 207` in the scenario's three runs. The skill asked for a plan change. |
| [`20261028T164836Z_t26`](runs/20261028T164836Z_t26/report.md) | the skill, final approved plan | Apply of plan v2 **on the same database**, so on top of v1's state: `op_080` `updated`, the new `op_120` `adopted`, the other ten `unchanged`. Ten scenarios: `t26_cancel_substitute` failed again on the PAC's 207; `t26_cancel_retry`, about nine minutes later with no configuration change, passed; `t26_sat_xml_export` failed at the trial balance (`KeyError: column_groups`). Eight of nine screenshots, at 1161 x 633. |
| [`20261028T170124Z_t26r`](runs/20261028T170124Z_t26r/report.md) | **re-run by the project's maintainer session, not by the skill** | New database `t26r`, the final approved plan unchanged: 5 `created`, 6 `adopted`, 1 `unchanged` with `pre_state`. The nine scenarios except `t26_cancel_retry` (tied on purpose to the record ids of the skill's run): eight passed at once, **including the automatic cancellation**; `t26_sat_xml_export` failed at the trial balance as before. Then the maintainer version of that scenario ([scenarios_maintainer_rerun/](scenarios_maintainer_rerun/)), written with `check`, passed, and the two XML files are in [files/](runs/20261028T170124Z_t26r/files/). A second apply changed nothing. Eight screenshots, at 1228 x 662. |

Plan v1 itself is not in this folder (plan.json was edited in place); the first run's `apply.json` records its hash.

## What the author contributed

No manual UI work. The author's part:

1. **The requirement.**
2. **One answer at intake.** Standard Odoo does not stop a clerk from stamping when a customer's fiscal data is
   incomplete: with an RFC but no fiscal ZIP the invoice silently goes out to the general public, and a missing regime
   defaults to 601 and the PAC rejects it. The skill offered an automated rule (an `ir.actions.server` with a short
   **Python** snippet that refuses to post) or standard behaviour plus a documented check. The author chose the rule,
   the skill's recommendation (the author's review session, a separate Claude Code session the author used to review
   plans before approving, also recommended it: there is no standard alternative). The plan therefore carries custom
   code: `op_110_cfdi_guard_action`.
3. **The first approval, with a change to the Test plan for need 6:** before leaving the SAT files as Not tested,
   try to generate both XML files over RPC through the trial balance's public handler methods, and report the exact
   error if it fails.
4. **The choice that produced plan v2.** For the "Publico en General" defect the skill offered (a) renaming the
   customer or (b) a monthly global invoice for anonymous counter sales. The author chose **(b)**: anonymous
   counter sales go into the monthly global invoice, a customer who asks for an invoice in their name gets a
   nominative one; and archive the stray account. The author also asked to separate the cancellation's cause with
   a retry of the same document minutes later, to state in the report that the XML content could not be verified
   and not work around it, and to take the screenshots in the final run.
5. **The second approval, with two corrections that changed no op:** "Not covered" still said the global invoice
   was not configured; and a retry that works does not tell "too soon after stamping" from "a transient failure of
   the test service", only a second failure would rule out the timing.

The skill showed the plan at the first review stop **condensed** ("the prose of decisions 6 to 9" summarized); the
skill's rules ask for plan.md in full. That is a deviation of the skill, noted here.

Agent time: about 27 minutes (including a 5-minute wait before the cancellation retry) and 366,325 new tokens, not
counting the author's time at the three stops.

## Requirement against tests

| Need | Proved by | Gap |
|---|---|---|
| 1. Stamped CFDI 4.0 with the customer's RFC, regime, ZIP, CFDI use and 16% IVA | `t26_invoice_nominative_pue`: use G01, 16% IVA, stamped with a UUID | |
| 1. Sales to the general public with the generic RFC | `t26_global_invoice`: two anonymous counter sales posted unstamped, then one monthly global invoice stamped to the generic RFC with both | |
| 1. Incomplete fiscal data found before stamping | `t26_fiscal_data_guard`: posting is refused (`expect_error`, `UserError`) for an RFC without ZIP, a regime that does not fit the RFC and a PUE invoice without payment way; the invoice stays a draft without UUID; once fixed it posts | Rests on the plan's Python rule, not on standard configuration |
| 2. Counter sales PUE with the actual payment way | `t26_invoice_nominative_pue`, `t26_global_invoice`: payment ways 03, 04, 01 and 28 | |
| 2. Credit customers PPD, one stamped payment receipt per payment, partial ones included | `t26_ppd_two_partial_payments`: 11,600 PPD; 5,000 by bank and 6,600 cash, each with its own stamped complement and the remaining balance | |
| 3. A return or discount is a stamped credit note related to the invoice | `t26_credit_note`: `out_refund` with `reversed_entry_id`, origin `01\|…`, stamped | |
| 4. Cancel with the SAT reason and replace with an invoice that references it; the cancelled one stays visible | `t26_cancel_substitute`: the replacement is stamped with origin `04\|<UUID>`, and Odoo then cancels the original itself with reason 01 | **The test PAC's automatic cancellation is intermittent.** In the skill's session it was refused with `Code : 207` ("Cancelling got an error") in 3 of the 4 times the automatic cancellation ran; a retry of the same document about nine minutes later worked. In the maintainer re-run it worked at once. The cause is open: "too soon after stamping" and "a transient failure of the test service" are both consistent with these observations, and none of them rules either out. |
| 5. Fee bills withhold 10% ISR and two thirds of the IVA, on the bill and in the accounts | `t26_fees_bill_withholdings`: 10,000 → -1,000 ISR, -1,066.67 IVA withheld, total 9,533.33; after payment, the cash-basis entry moves the withheld IVA to "effectively paid" | |
| 6. SAT chart of accounts with grouping codes | `t26_sat_coa_readiness` (every active account of company 4 has a valid SAT code and a nature tag); in the maintainer re-run, `t26_sat_xml_export` reads the generated XML: RFC `IVD920810GU2`, month 10, year 2026, 42 accounts, grouping code `102` for account 102 ([XML](runs/20261028T170124Z_t26r/files/t26_sat_xml_export_chart_of_accounts.xml)) | In the skill's runs the file was generated but its content not read |
| 6. SAT trial balance | maintainer re-run only: generated with the report's own options and read back: RFC, month 10, year 2026, 42 accounts ([XML](runs/20261028T170124Z_t26r/files/t26_sat_xml_export_trial_balance.xml)) | **Not tested in the skill's runs** (`KeyError: column_groups`) |

Also outside the plan, as plan.md says: production PAC credentials and the company's own CSD, customer fiscal data
as master data, and generating the monthly files from the menu (Accounting > Reporting > Trial Balance).

A finding about Odoo itself: the `l10n_mx` chart template of 20.0 creates an account with code `171.16000`, which
is not a valid SAT code. Row 59 of `odoo/addons/l10n_mx/data/template/account.account-mx.csv` is an account
subgroup with an empty `active`, where the other 182 subgroups have `False`, so it becomes an active account. The
plan archives it (`op_120_archive_stray_account`). The 19.0 template has no subgroups.

## How the session ran

Permission mode: **`auto`** (all 53 permission-mode records of its transcript; measured from the session transcript on
2026-10-28, and the transcript is not kept). The session was launched with `--allowedTools "Bash(ofa *)"`, which the
maintainer had suggested as if it limited the session to `ofa`; it did not: 89 of its 91 shell commands were not a
plain `ofa` command (`cd … && ofa …`, `grep`, `sed`, `python3` on the Odoo source), and the mode approved them,
including a `sleep 300` before the cancellation retry, without the author seeing a prompt. Later example sessions are
launched without that option. The plugin's guard hook did run on every command and refused the in-page `.click()`. The
guard does not depend on the permission mode (see "The permission mode is not a layer" in `docs/guard.md`).

## Screenshots

The skill took 8 of 9 (one target's record had changed by then), at 1161 x 633: it could not set the window size
("System access is required"). The maintainer measured afterwards that `set_viewport_size` has never resized
anything on this setup: every screenshot of examples 1 to 3 is 1228 x 662, although the older MCP version answered
success. The procedure no longer asks for a fixed size (`38dc7ac`).

From the maintainer re-run:

- [Cancelled invoice](runs/20261028T170124Z_t26r/screenshots/t26_cancel_substitute_cancelled_invoice.png): CFDI
  status Cancelled, "Substituted By" the replacement; and
  [the replacement](runs/20261028T170124Z_t26r/screenshots/t26_cancel_substitute_replacement_invoice.png), signed,
  CFDI origin `04|<UUID of the original>`.
- [Credit note](runs/20261028T170124Z_t26r/screenshots/t26_credit_note_credit_note.png): signed, origin
  `01|<UUID>`.
- [Fee bill](runs/20261028T170124Z_t26r/screenshots/t26_fees_bill_withholdings_fees_bill.png): the line with 10%
  ISR, 10.67% IVA withheld and 16% IVA; the totals are below the visible area and in `records.json`.
- [Anonymous counter sale](runs/20261028T170124Z_t26r/screenshots/t26_global_invoice_anonymous_cash_invoice.png):
  CFDI to public, cash, "Signed Global".
- [Nominative PUE invoice](runs/20261028T170124Z_t26r/screenshots/t26_invoice_nominative_pue_pue_transfer_invoice.png):
  transfer, use G01 (acquisition of merchandise), signed.
- [PPD invoice](runs/20261028T170124Z_t26r/screenshots/t26_ppd_two_partial_payments_ppd_invoice.png), paid in two
  payments, and [the first payment](runs/20261028T170124Z_t26r/screenshots/t26_ppd_two_partial_payments_complement_1.png)
  with its signed payment complement.

The company switcher shows the admin's current company (San Francisco); every record belongs to company 4 (MXN).

## Verdict on the fourth v1 area

"On a fresh demo database, from a written requirement covering at least one v1 area, the agent produces a
reviewable plan, applies it and runs functional tests that pass, without manual UI work by the author."

Met for the Mexican localization, with the gaps above: the plan validated and passed the lint gate, stamped and
cancelled against a real test PAC, and the author did no UI work. The skill's final run was not on a fresh
database and had two failing scenarios, one caused by the test PAC and one by an `ofa` limit; the maintainer re-run
on a fresh database passes all nine, with the SAT files read back through the `check` step added afterwards. The
fiscal-data check rests on custom Python code the author chose.
