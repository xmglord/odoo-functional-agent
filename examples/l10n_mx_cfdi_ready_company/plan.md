# Casa Albar: CFDI 4.0 invoicing, payment complements, fee withholdings and SAT month-end files

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise
- Areas: l10n_mx, accounting

## Summary
Casa Albar wants every fiscal document issued and stamped from Odoo instead of an external portal. Most of what it
asks is standard `l10n_mx_edi` behaviour on a company that already has RFC, regime and CSD: CFDI 4.0 invoices, PUE/PPD,
payment complements, credit notes related by UUID, cancellation with substitution. The plan adds what the template
lacks: payment journals that post entries (needed for complements and for withholdings to move on payment), a payment
way per journal, a "Publico en General" customer, a fees product with the two withholdings, the SAT reports module,
and one automation rule that stops an invoice with incomplete customer fiscal data before it can be stamped.

The company is used as it is: demo company `base.demo_company_mx` (id 4, RFC `IVD920810GU2`, regime 601, PAC Quadrum
in test mode, demo CSD valid until 2027-05-18) plays Casa Albar. The plan does not rename it or touch its fiscal data.

## Decision 1: Stamped CFDI 4.0 invoices with the customer's fiscal data (standard)
- Ops: none (standard behaviour, proved by scenarios).
- Decision: the clerk keeps each customer's RFC (`res.partner.vat`), regime (`res.partner.l10n_mx_edi_fiscal_regime`),
  fiscal ZIP (`res.partner.zip`) and CFDI use (`res.partner.l10n_mx_edi_usage`) on the customer; the invoice copies
  them and the "Send" button stamps it with the company's PAC (`account.move.action_send_and_print`, extra EDI
  `mx_cfdi`). Products sold carry the 16% sales IVA (`account.4_tax12`, the company default) and an UNSPSC code
  (`product.template.unspsc_code_id`).
- Business reason: requirement 1. The company is already configured (`res.company.l10n_mx_edi_pac` = `finkok`,
  `l10n_mx_edi_pac_test_env` = true, a valid `certificate.certificate` with `scope` `cfdi_csd`).
- What Odoo does: `account.move.l10n_mx_edi_cfdi_state` becomes `sent`, `l10n_mx_edi_cfdi_uuid` holds the fiscal
  folio, and a `l10n_mx_edi.document` row in state `invoice_sent` keeps the XML.
- Pre-state: all of the above already holds on company 4 in the template.
- Alternatives: none needed; a production go-live only switches `l10n_mx_edi_pac_test_env` off and enters the PAC
  credentials (`l10n_mx_edi_pac_username`, `l10n_mx_edi_pac_password`).
- Pitfalls: a product without UNSPSC code blocks the CFDI; usage `P01` is no longer valid in 4.0.
- Sources: `knowledge/20.0/l10n_mx/cfdi_configuration_pac_csd.md`, `knowledge/20.0/l10n_mx/fiscal_data_rfc_regime.md`,
  `knowledge/20.0/l10n_mx/cfdi_usage_payment_way_policy.md`

## Decision 2: Anonymous counter sales in a monthly global invoice
- Ops: [op_080_public_partner]
- Decision: anonymous counter sales are invoiced to one customer "Ventas de mostrador" (country Mexico, no RFC, CFDI
  use `S01`), posted with their payment way but **not stamped one by one**. At month end the clerk selects them and
  runs "Create Global Invoice" (`account.move.l10n_mx_edi_action_create_global_invoice`, wizard
  `l10n_mx_edi.global_invoice.create`, periodicity `04` monthly), which stamps one CFDI to `XAXX010101000` "PUBLICO
  EN GENERAL" with the InformacionGlobal node. A customer who asks for an invoice in their own name is invoiced
  nominatively like any other customer (Decision 1).
- Business reason: requirement 1, "sales to the general public go out with the generic RFC". Changed after the
  first run: an individual invoice to a partner named "Publico en General" was rejected by the PAC with
  `CFDI40130` (receiver name "PUBLICO EN GENERAL" requires the InformacionGlobal node, i.e. a global invoice). A
  diagnostic run with a partner without RFC under another name stamped fine, which confirmed the cause. The user
  chose the global invoice (option b) over renaming only.
- What Odoo does: the selected invoices get `l10n_mx_edi_cfdi_state` = `global_sent`; one `l10n_mx_edi.document`
  in state `ginvoice_sent` lists them in `invoice_ids`. The partner is renamed from "Publico en General" so the name
  never reaches the receiver node of an individual CFDI.
- Pre-state: the partner was created by the first apply; this apply renames it (`updated`).
- Alternatives: rename only and stamp each ticket to `XAXX010101000` under the buyer's name (option a, rejected).
- Pitfalls: invoices already stamped one by one cannot enter a global invoice; credit notes on a global invoice
  must reference it (`is_refund_gi` path, not tested here). The guard of Decision 3 still requires a payment way on
  each anonymous PUE invoice.
- Sources: `knowledge/20.0/l10n_mx/cfdi_usage_payment_way_policy.md`, `knowledge/20.0/l10n_mx/fiscal_data_rfc_regime.md`

## Decision 3: Stop incomplete fiscal data before stamping
- Ops: [op_010_install_automation] [op_100_cfdi_guard_rule] [op_110_cfdi_guard_action]
- Decision: an Automation Rule (`base.automation`, trigger `on_create_or_write` on `account.move.state`, from not
  posted to posted, Mexican customer invoices and credit notes with `l10n_mx_edi_is_cfdi_needed`) runs a server
  action (`ir.actions.server`, `state` = `code`) that raises a `UserError` and so refuses the posting when:
  - the customer has an RFC but no country;
  - a Mexican customer with RFC has no fiscal ZIP or no regime;
  - the regime does not fit the RFC: a 13-character RFC (individual) with a legal-entity-only regime (601, 603,
    620, 622, 623, 624), or a 12-character RFC (legal entity) with an individual-only regime (605 to 616, 621, 625);
  - a PUE invoice has no payment way (`account.move.l10n_mx_edi_payment_method_id`).
  Generic RFCs `XAXX010101000` and `XEXX010101000` and customers without RFC are not checked.
- Business reason: requirement 1, "the clerk must find out before stamping, not from a rejection". Standard Odoo
  does not do this (checked in the 20.0 source):
  - a customer with RFC but no ZIP makes `l10n_mx_edi_cfdi_to_public` true and read-only
    (`_compute_l10n_mx_edi_cfdi_to_public`), so the invoice is stamped silently to "publico en general" instead of
    to the customer: no warning, no rejection, a wrong CFDI;
  - a Mexican customer's regime defaults to `601`, so an individual left at the default is rejected by the PAC;
  - a PUE invoice without payment way is rejected by the PAC (`CFDI40223`).
  Posting is the last step before stamping, so refusing it there tells the clerk what to fix while nothing has been
  sent.
- What Odoo does: the rule's message names the invoice, the customer and each missing item.
- Pre-state: `base_automation` is not installed in the template.
- Alternatives: training the clerk to look at the read-only "Publico en General" checkbox on the invoice form
  (rejected by the user in favour of a hard stop); a custom module with a Python constraint (needs development and
  deployment; the rule does the same and is editable from Settings > Technical > Automation Rules).
- Pitfalls: the rule carries a 25-line Python snippet; it is configuration in the UI but it is code, and whoever
  maintains it should review it on Odoo upgrades. The regime and RFC length test is a plausibility check, not a
  lookup of the SAT registry: the PAC still validates the real data. The rule also fires on a credit note, which is
  intended (a credit note to a customer with broken data would be rejected too).
- Sources: `knowledge/20.0/l10n_mx/fiscal_data_rfc_regime.md`, `knowledge/20.0/l10n_mx/cfdi_usage_payment_way_policy.md`.
  The automation part is uncited: no compendium entry; names checked with
  `ofa inspect --target t26 ir.actions.server --fields state,code,usage,model_id,name` and the 20.0 source of
  `base_automation` (`base.automation.trigger`, `filter_pre_domain`, `filter_domain`, `trigger_field_ids`,
  `ir.actions.server.base_automation_id`).

## Decision 4: Counter sales PUE with the real payment way; payment ways on payment journals
- Ops: [op_060_bank_payment_way] [op_070_cash_payment_way]
- Decision: counter sales are invoiced with the immediate payment term, so `account.move.l10n_mx_edi_payment_policy`
  is `PUE`, and the clerk sets the payment way on the invoice (`l10n_mx_edi.payment_method_efectivo` 01,
  `payment_method_transferencia` 03, `payment_method_tarjeta_de_credito` 04 or `payment_method_tarjeta_debito` 28).
  The bank journal defaults to 03 and the cash journal to 01 (`account.journal.l10n_mx_edi_payment_method_id`), which
  is the payment way payments (and their complements) take by default.
- Business reason: requirement 2, first half. The payment way on a counter sale depends on the ticket, not on the
  customer, so it is not set on the partner nor on the sales journal; the guard of Decision 3 makes sure it is not
  forgotten.
- Pre-state: no journal of company 4 has a payment way (checked with `ofa inspect account.journal`).
- Alternatives: a separate card-terminal journal with payment way 04, when card settlements are reconciled apart
  from transfers.
- Pitfalls: payment way on the sales journal (`account.4_sale`) would silently fill every invoice, including the
  wrong ones; it is left empty on purpose.
- Sources: `knowledge/20.0/l10n_mx/cfdi_usage_payment_way_policy.md`

## Decision 5: Credit customers PPD with a payment complement per payment
- Ops: [op_030_bank_inbound_outstanding] [op_040_cash_inbound_outstanding]
- Decision: each 30-day credit customer gets the 30-day term (`res.partner.property_payment_term_id` =
  `account.account_payment_term_30days`) and payment policy `PPD` on the partner
  (`res.partner.l10n_mx_edi_payment_policy`). The bank and cash inbound payment methods get the Outstanding Receipts
  account (`account.payment.method.line.payment_account_id`) so payments post a journal entry. After each payment is
  reconciled the clerk presses "Update Payments" on the invoice
  (`account.move.l10n_mx_edi_cfdi_invoice_try_update_payments`), which stamps one complement per payment with the
  amount paid and the remaining balance.
- Business reason: requirement 2, second half. PPD on the partner, not only the term: Odoo infers PPD from the term
  only when the due date falls in a later month, so an invoice dated the 1st with 30 days would come out PUE.
- What Odoo does: the PPD invoice says `MetodoPago=PPD`, `FormaPago=99`; each payment gets a `l10n_mx_edi.document`
  in state `payment_sent` with its own UUID on `account.payment.l10n_mx_edi_cfdi_uuid`.
- Pre-state: the inbound manual methods of `account.4_bank` and `account.4_cash` have no payment account in the
  template; without it, with `account_accountant` installed, a payment has no entry and no complement.
- Alternatives: none for the complement itself. Per-customer settings are master data the clerk fills when the
  credit is granted; the plan does not create customers.
- Pitfalls: "Update Payments" is a step, not automatic; a payment dated in the future is skipped until its date.
- Sources: `knowledge/20.0/l10n_mx/payment_complements.md`, `knowledge/20.0/accounting/payment_terms.md`

## Decision 6: Returns and discounts as related credit notes (standard)
- Ops: none.
- Decision: returns and later discounts are credit notes made with "Credit Note" on the stamped invoice
  (`account.move.reversal`), then posted and stamped.
- Business reason: requirement 3.
- What Odoo does: reversing a stamped invoice writes `account.move.l10n_mx_edi_cfdi_origin` = `01|<UUID>` on the
  credit note (`_reverse_moves`), so the stamped egreso CFDI carries the relation (TipoRelacion 01) to the original.
  Payment policy of a credit note is always PUE.
- Pre-state: standard.
- Alternatives: a credit note created by hand with the origin typed in; error-prone, not recommended.
- Pitfalls: a credit note for a PPD invoice already paid needs the refund reconciled; not covered here.
- Sources: uncited: no compendium entry covers credit notes (listed as a gap in the l10n_mx index); names checked in
  the 20.0 source `l10n_mx_edi/models/account_move.py` (`_reverse_moves`) and with
  `ofa inspect --target t26 account.move.reversal --fields move_ids,reason,journal_id,date`.

## Decision 7: Cancellation with substitution (standard)
- Ops: none.
- Decision: a wrong invoice is handled from its "Request Cancel" button (`account.move.button_request_cancel`,
  wizard `l10n_mx_edi.invoice.cancel`): with reason `01` the wizard first creates the replacement invoice
  (`action_create_replacement_invoice`, origin `04|<UUID of the wrong one>`), which is posted and stamped; the wrong
  one is then cancelled with reason 01 (`action_cancel_invoice`). Reasons 02, 03 and 04 cancel without replacement.
- Business reason: requirement 4.
- What Odoo does: the cancelled invoice keeps its number and shows `l10n_mx_edi_cfdi_state` = `cancel` and
  `l10n_mx_edi_invoice_cancellation_reason`; in test mode the move itself goes to `state` = `cancel` right away; in
  production it waits for the SAT (and the customer's acceptance when required).
- Pre-state: standard.
- Pitfalls: a stamped invoice cannot be reset to draft; do not try to "fix" it in place.
- Sources: `knowledge/20.0/l10n_mx/cfdi_configuration_pac_csd.md`

## Decision 8: Professional fees bills with ISR and IVA withholdings
- Ops: [op_090_fees_product] [op_050_bank_outbound_outstanding]
- Decision: a purchase-only service product "Professional fees (honorarios)" with vendor taxes IVA 16%
  (`account.4_tax14`), IVA withheld 10.67% = two thirds (`account.4_tax8`) and ISR withheld 10% (`account.4_tax5`).
  Fees bills use this product. The bank outbound payment method gets the Outstanding Payments account.
- Business reason: requirement 5. The withholdings show as separate tax lines on the bill and post to their own
  accounts: ISR to "Taxes withheld from income tax for professional services" at once (`tax_exigibility`
  `on_invoice`); IVA withheld to the transition account "VAT withholding taxes" and, when the bill is paid, to "VAT
  withholding tax effectively paid" (cash basis, `on_payment`), the account the company pays the SAT from.
- Pre-state: no such product; the bank outbound manual method has no payment account.
- Alternatives: the chart's "Honorarium" fiscal position maps IVA 16% to `16% VAT 2/3 H`, which splits the IVA into
  creditable and "Honorarium VAT due" accounts but shows no withholding on the bill (the bill total includes the full
  IVA). It does not meet "the withholdings must show on the bill", so it is not used.
- Pitfalls: the chart describes `10% WH I S` as ISR "on salaries"; it is the 10% rate and its account is the
  professional-services ISR account, so it fits fees. Check the label with the accountant.
- Sources: `knowledge/20.0/l10n_mx/iva_and_withholdings.md`

## Decision 9: SAT electronic accounting from the Trial Balance
- Ops: [op_020_install_mx_reports] [op_120_archive_stray_account]
- Decision: `l10n_mx_reports` adds two buttons to Accounting > Reporting > Trial Balance for a Mexican company:
  "COA SAT (XML)" (catalogo de cuentas, with the grouping code taken from the first 6 characters of each account
  code, e.g. `102.01`, and nature D/A from the account tags `l10n_mx.tag_debit_balance_account` /
  `l10n_mx.tag_credit_balance_account`) and "SAT (XML)" (balanza de comprobacion, normal or supplementary, also
  month 13). Both are signed with the company's CSD when it is valid.
- Business reason: requirement 6, without a spreadsheet.
- Pre-state: the module is already installed in the template (auto-install with `l10n_mx` and `account_reports`),
  so the op reports `unchanged` and proves only that it is there. All 150 accounts of company 4 carry a nature tag
  (110 debit, 40 credit, measured with `ofa inspect account.account`).
- Pitfalls: a new account whose code is not `NNN.NN[.N]` (`account.account.l10n_mx_is_sat_invalid`) or has no
  nature tag blocks or warns the export; new accounts must follow the SAT grouping.
- Stray template account, [op_120_archive_stray_account]: the first run found that the `mx` chart template
  creates account "Accumulated depreciation of machinery and equipment for power generation from renewable sources
  or efficient co-generation systems" with code `171.16000` from a subgroup row
  (`l10n_mx/data/template/account.account-mx.csv` line 59); `l10n_mx_is_sat_invalid` is true for it. It has no
  entries and the real account is `171.16.01`, so it is archived (`account.account.active` = false), which takes
  it out of the SAT check. 149 active accounts remain.
- Sources: `knowledge/20.0/l10n_mx/INDEX.md` (lists `l10n_mx_reports` as not covered by an entry); uncited for the
  rest; names checked in the 20.0 source `l10n_mx_reports/models/trial_balance.py` and `account_account.py`.

## Test plan
Scenarios to write after the apply. All run in company 4 and stamp with the Quadrum test PAC (network needed).

| Need (from requirement.md) | Scenario | What it checks |
|---|---|---|
| 1. Stamped CFDI 4.0 with customer RFC, regime, ZIP, use, 16% IVA | t26_invoice_nominative_pue | invoice to demo customer `l10n_mx_edi.demo_partner_quadrum_1` with use G01, amount_tax = 16% of base, `l10n_mx_edi_cfdi_to_public` false, `l10n_mx_edi_cfdi_state` sent, UUID set, document `invoice_sent` |
| 1. General public with generic RFC | t26_global_invoice | two anonymous invoices to "Ventas de mostrador" (cash 01 and debit card 28), posted, not stamped; `l10n_mx_edi_cfdi_to_public` true; global invoice wizard monthly: both invoices `l10n_mx_edi_cfdi_state` = `global_sent`, one document `ginvoice_sent` with both in `invoice_ids` and `attachment_uuid` set |
| 1. Incomplete fiscal data found before stamping | t26_fiscal_data_guard | fictional customers: RFC without ZIP, 13-char RFC with regime 601, and a complete customer on a PUE invoice without payment way; each `action_post` refused with `UserError` "Incomplete CFDI data", invoice stays `draft` with no UUID; after fixing the data it posts |
| 2. Counter sale PUE with real payment way (transfer, card, cash) | t26_invoice_nominative_pue, t26_global_invoice | PUE invoices stamped with payment way 03 (transfer) and 04 (credit card); cash 01 and debit card 28 on the anonymous invoices of the global invoice |
| 2. Credit customer PPD, complement per payment incl. partials, with remaining balance | t26_ppd_two_partial_payments | customer with 30-day term and PPD; invoice 11,600 PPD stamped; payment 1 of 5,000 by bank, Update Payments, complement `sent` and residual 6,600; payment 2 of 6,600 in cash, complement `sent`, invoice `paid`; two `payment_sent` documents with distinct UUIDs |
| 3. Return or discount = stamped credit note related to the original | t26_credit_note | reversal of a stamped invoice: `move_type` out_refund, `reversed_entry_id` = invoice, `l10n_mx_edi_cfdi_origin` starts with `01|`, stamped (`sent`, UUID) |
| 4. Cancel with SAT reason and substitute; cancelled stays visible with reason | t26_cancel_substitute, t26_cancel_retry | wrong invoice stamped; replacement created by the wizard with origin `04|`, posted, stamped; stamping it makes Odoo cancel the original with 01 by itself; original: `l10n_mx_edi_cfdi_state` cancel, `l10n_mx_edi_invoice_cancellation_reason` 01, `state` cancel, still found by search. If the test PAC refuses the cancel (`invoice_cancel_failed`), t26_cancel_retry retries the same document (`l10n_mx_edi.document.action_retry`) a few minutes later, with no configuration change, and the report reads it this way: a retry that succeeds does not tell "too soon after stamping" from "transient test-service failure" (both stay open); only a second failure, minutes after stamping, rules out timing and points to the test service |
| 5. Fees bill withholds 10% ISR and 2/3 IVA, on bill and in accounts | t26_fees_bill_withholdings | bill 10,000 with the fees product: amount_tax -466.67, total 9,533.33; tax lines -1,000.00 on the ISR account and -1,066.67 on the IVA withheld transition account; after payment by bank, a cash-basis entry moves 1,066.67 to "VAT withholding tax effectively paid" |
| 6. SAT chart of accounts with grouping codes | t26_sat_coa_readiness, t26_sat_xml_export | readiness: in company 4 the 149 active accounts (after [op_120_archive_stray_account]) have `l10n_mx_is_sat_invalid` false and a nature tag. Export: `account.report.dispatch_report_action` on the Trial Balance with `action_l10n_mx_generate_coa_sat_xml` must run without error. **XML content not verified**: an ofa `call` step discards the method's return value, so RFC, period and grouping codes inside the file cannot be asserted |
| 6. SAT trial balance | **Not tested** | `action_l10n_mx_generate_sat_xml` through `dispatch_report_action` fails with `builtins.KeyError: column_groups`: it needs the full options from `account.report.get_options`, which a scenario cannot pass on (call results are discarded). Kept in t26_sat_xml_export to record the error |

## Not covered by this plan
- Production stamping: PAC credentials and the real CSD of Casa Albar (Accounting > Configuration > Settings >
  Mexican Electronic Invoicing). The demo company stays in PAC test mode.
- Customers' fiscal data, credit terms and PPD policy are master data the clerk enters per customer; the plan creates
  only the "Publico en General" customer.
- The monthly SAT XML files are produced from the UI (Accounting > Reporting > Trial Balance > "COA SAT (XML)" and
  "SAT (XML)"); ofa cannot press a report download.
- DIOT and XML polizas are not requested and not configured. (The global invoice is configured: Decision 2.)

## Glossary
- **CFDI**: the SAT electronic invoice XML; `l10n_mx_edi.document` in Odoo.
- **PAC**: SAT-authorized stamping provider (`res.company.l10n_mx_edi_pac`).
- **PUE / PPD**: paid in one payment / paid in installments or later (`account.move.l10n_mx_edi_payment_policy`).
- **Complemento de pago**: CFDI type P stamped for each payment of a PPD invoice.
- **CFDI de egreso**: credit note CFDI (`out_refund`), related to the original by UUID.
- **Honorarios**: professional fees billed by an individual; the payer withholds ISR and two thirds of the IVA.
- **Codigo agrupador**: SAT grouping code, the first segment(s) of each account code.
