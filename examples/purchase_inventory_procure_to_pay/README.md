# Example 2: Purchase + Inventory, procure to pay

A fictional food and cleaning-supplies distributor, Harbor Fresh Distribution, wants purchasing and its warehouse in
Odoo 20, from the purchase order to the vendor bill. The author wrote the requirement
([requirement.md](requirement.md)) and ran the `odoo-functional` skill on it in one interactive Claude Code session
(2026-10-27, 17:27 to 22:57 UTC), on a fresh demo database `t24` provisioned by the skill.

What to look at, in order:

1. [requirement.md](requirement.md): the business requirement, six numbered needs.
2. [plan.md](plan.md): the decisions with their business reasons, the two accepted deviations, the **Test plan**
   (which scenario proves which need, and which needs are not tested) and "Not covered".
3. [plan.json](plan.json): the 24 operations `ofa` applied; [plan.approved](plan.approved) holds the hash of the
   approved version.
4. [scenarios/](scenarios/): the six functional tests the skill wrote.
5. The two runs below, each with a `report.md`.

## What changed in the skill since example 1

Between [example 1](../sales_crm_quote_to_cash/README.md) and this session the skill and `ofa` changed in two ways
that this example exercises:

- **Test plan** (`5720807`). plan.md now carries a table of need, scenario and what it checks, with the needs that
  will not be tested marked **Not tested** and the reason. The author sees it at the review stop, before approving.
  The final report repeats it with pass or fail and lists every difference from the approved table.
- **Scenario `company` key** (`8904457`). A scenario, step or evidence item can name the company it runs in; every
  scenario here sets `"company": {"$ref": "base.main_company"}`. In example 1 its absence made the evidence read the
  customer balance in the wrong company.

## Runs

| Run | Who | What happened |
|---|---|---|
| [`20261027T225301Z_t24`](runs/20261027T225301Z_t24/report.md) | the skill | First apply on the fresh database: 19 `created`, 2 `updated` (settings), 2 `adopted` (the warehouse and its receipt type), 1 `unchanged` with `pre_state` (`op_040_lots`: lots were already on in the template, so that op proves nothing). Five scenarios ran: four passed, `hf_lots_fefo` failed (see below). The skill then added `hf_lots_fefo_recheck` and ran it alone into the same run; it passed. One screenshot. |
| [`20261027T230728Z_t24r`](runs/20261027T230728Z_t24r/report.md) | **re-run by the project's maintainer session, not by the skill** | Same approved plan, unchanged, on a new database `t24r`: apply with the same statuses as the first run, then the five scenarios in one `ofa test` call (all pass, including the corrected `hf_lots_fefo`), then `hf_lots_fefo_recheck` alone into the same run (pass), the same sequence the skill used. Eight screenshots, one per target, taken by the maintainer with the skill's procedure and checked against their records. |

Screenshots, all from the maintainer run:

- [The automatic RFQ](runs/20261027T230728Z_t24r/screenshots/hf_auto_replenishment_auto_rfq.png): 110 floor
  cleaner to Brightside at 7.50.
- [The partial receipt](runs/20261027T230728Z_t24r/screenshots/hf_receive_partial_and_bill_partial_receipt.png)
  (6 at WH/Input, done) and
  [its backorder](runs/20261027T230728Z_t24r/screenshots/hf_receive_partial_and_bill_backorder.png)
  (4, ready, same source order).
- [The bill for what was received](runs/20261027T230728Z_t24r/screenshots/hf_receive_partial_and_bill_bill_received_qty.png)
  (6 at 6.00, posted) and
  [the over-billing draft](runs/20261027T230728Z_t24r/screenshots/hf_receive_partial_and_bill_bill_over_billed.png)
  (4 more). The form does not show `release_to_pay`; its value is in `records.json`.
- [Lot HF-EARLY](runs/20261027T230728Z_t24r/screenshots/hf_lots_fefo_lot_early.png) and
  [the FEFO delivery](runs/20261027T230728Z_t24r/screenshots/hf_lots_fefo_fefo_delivery.png) (the recheck's target
  is the same delivery). The reserved lot is behind "Details"; the assertion on the move line proves it.

Two things in the screenshots are display, not data: the expiry shows as Mar 30, 2027, 6:00 PM because the web client
shows the stored 2027-03-31 00:00 UTC in the admin user's timezone, and the company switcher shows the admin's
current company (the Mexican one) while every record belongs to San Francisco (`YourCompany`, USD).

Not in this folder: a maintainer second apply of the plan on `t24` right after the session (all 24 `unchanged`),
which wrote an apply-only run. The skill itself did not run a second apply this time.

Why the second run exists:

- **The skill's run lost its evidence.** At the time, each `ofa test` into a run rewrote `test.json`, `records.json` and
  `screenshot_targets.json`. The recheck therefore replaced the five main scenarios' results, evidence and screenshot
  targets; only [test_history.jsonl](runs/20261027T225301Z_t24/test_history.jsonl) kept both calls, and the report lists
  the first call under "Earlier `ofa test` invocations". Of the eight screenshot targets the scenarios declare (seven in
  the five main scenarios, one in the recheck), only the recheck's survived, so the skill took one screenshot. `ofa` now
  keeps every scenario's latest results, evidence and targets in a run (`f73bd3c`); the maintainer run shows all six
  scenarios after the same two calls.
- **The corrected `hf_lots_fefo` had never run in full.** It failed at step `s260` with
  `lot_id of id 112: expected eq [6], got 6`: the scenario stored a search result (a list of ids) in a variable and
  compared a many2one field, which reads a single id, against that list. Lot 6 was the right lot, HF-EARLY. The
  skill fixed `s260` but did not rerun the scenario, because it would collide with the lots already on the database;
  it added the read-only `hf_lots_fefo_recheck` instead. The maintainer run is the first full pass of the fixed file.

## What the author contributed

The success criterion asks for no manual UI work by the author, and there was none. Unlike example 1, there was also
no functional correction this time: the plan the skill wrote is the plan that was applied.

1. **The requirement.**
2. **Two answers at intake**, to the skill's questions; both are the skill's recommendation:
   - Approval threshold: Odoo compares the threshold with the order total including tax, not before tax. The author
     chose "50,000 on the taxed total", which is stricter than asked, never looser.
   - Vendor proposal: Odoo does not propose the cheapest vendor across vendors; it takes the largest quantity break
     the order reaches. The author chose "native rule, documented", with a counter-example tested.
   - Free comment: "do not continue, wait until I say". The skill stopped and resumed on "sigue con el plan".
3. **One approval**, the message "aprobado", after reading plan.md and its Test plan. The author asked for no change.

The skill chose the company without asking: the requirement names no country, and the plan works in the main demo
company (San Francisco, USD, 15% purchase tax), stated in plan.md's header. In example 1 the skill asked.

The session was resumed once, at the review stop: the author left it waiting for approval, relaunched it with the same
flags and approved. The transcript shows the Claude Code version changing between the plan (2.1.311) and the approval
(2.1.312), and the browser and `ofa` working after the resume.

Agent time: about 15 minutes (11 to plan, 4 to apply, test and report) and 329,637 new tokens, not counting the
author's 5 hours 14 minutes at the review stop.

Permission mode: not measured. The session transcript was deleted at cleanup, before the T26 audit showed
that the mode, not the launch command's `--allowedTools`, decided which commands ran without a prompt.

## Requirement against tests

| Need | Proved by | Gap |
|---|---|---|
| 1. Orders of 50,000 or more need the purchasing manager's approval | `hf_po_approval`: the company has `two_step` approval at 50000 | **Not tested: no order goes through `to approve`.** Every scenario runs as the `ofa_bot` user, which is a purchase manager and skips the threshold. The Test plan said so before approval. The threshold is on the taxed total (accepted deviation) |
| 2. Vendors with price, minimum quantity and lead time; the cheapest one proposed | `hf_vendor_proposal`: the vendor lines read back; the proposed vendor is Bayline at 50, Northpoint at 200, Coastal at 600; "order once" at 200 gives a draft RFQ to Northpoint at 1.00 | **Not the cheapest at 600**: Coastal (1.10) instead of Northpoint (1.00), the documented counter-example. Proved through the replenishment rule only; on a purchase order made by hand the buyer picks the vendor |
| 3. Below the minimum, an RFQ up to the maximum, prepared automatically | `hf_auto_replenishment`: confirming a delivery of 10 with no stock prepares a draft RFQ line of 110 to Brightside at 7.50, linked to the rule | |
| 4. Two-step receipt; a partial delivery stays pending on the same order | `hf_receive_partial_and_bill`: 6 of 10 received at WH/Input without a wizard, a backorder of 4 on the same order, the put-away leaves 6 in WH/Stock, `receipt_status` `partial` | |
| 5. Lots with expiry recorded at receipt; first to expire goes out first | `hf_lots_fefo`: two lots received with their expiry dates read back; a delivery of 10 reserves HF-EARLY, not the earlier-received HF-LATE | First full pass only in the maintainer run |
| 6a. Bill only what was received | `hf_receive_partial_and_bill`: the bill line is 6, `release_to_pay` `yes`, posted | |
| 6b. Accounts Payable sees a quantity or price difference | `hf_receive_partial_and_bill`: price 6.50 gives `exception`, back to 6.00 gives `yes`; a second bill for 4 more gives `exception` | |
| 6c. Payment blocked until the difference is resolved | | **Not tested**: 3-way matching flags the bill (`release_to_pay`) but Odoo does not block its payment |
| "about 30 vendors" | | **Not covered**: the plan creates five fictional vendors and three products; importing the rest is outside it |

Also outside the plan: buyer and manager users (Settings > Users), which the plan lists as UI work for whoever adopts
it, and a hard payment block, which would need a customization.

## Verdict on the second v1 area

"On a fresh demo database, from a written requirement covering at least one v1 area, the agent produces a
reviewable plan, applies it and runs functional tests that pass, without manual UI work by the author."

Met for Purchase + Inventory, with the gaps above: fresh database, a written requirement, a plan that validated and
passed the lint gate with no warnings, an apply and a second apply that changed nothing, scenarios that pass, and no
UI work or functional correction by the author. The Test plan made the two untested needs visible before approval.
Need 1's approval flow is configured but not proved, because `ofa` can only act as its own bot user.
