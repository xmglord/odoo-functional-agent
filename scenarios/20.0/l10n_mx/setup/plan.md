# Mexican localization fixture: new MX subsidiary and payment complements

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise (`l10n_mx_edi` and its settings are Enterprise; the demo template is enterprise)
- Areas: l10n_mx, accounting
- Scenarios it supports: `scenarios/20.0/l10n_mx/l10n_mx_company_chart_autoload.json`,
  `scenarios/20.0/l10n_mx/l10n_mx_ppd_payment_complement.json`. The other two l10n_mx scenarios need no plan.

## Summary
The template already has two Mexican demo companies ready to stamp on the PAC test environments (company 4 with
Quadrum, company 5 with Solucion Factible, each with a demo CSD). The plan adds what the two flows need and the
template does not prove by itself: a new Mexican company created from scratch, which shows that the `mx` chart loads
on its own and which gets its CFDI settings through the Settings screen, and an outstanding account on company 4's
bank journal so that a customer payment posts a journal entry and can carry a payment complement.

## Decision 1: CFDI module
- Ops: [op_010_install_mx_edi]
- `l10n_mx_edi` is auto-installed with `l10n_mx` and is in the template, so the first apply reports this op
  `unchanged` with `pre_state: true`: it proves nothing about the plan and only states the dependency.

## Decision 2: New Mexican company, no separate chart load
- Ops: [op_020_mx_company]
- Creating a `res.company` with `country_id` Mexico runs `install_l10n_modules`, which loads the `mx` chart for it
  when the request commits. The plan therefore has no `call_method` for the chart (see the chart entry).
- The company gets currency MXN and a fictional fiscal ZIP (`06000`). It gets no RFC (`vat`) and no CSD: those come
  from the SAT for a real company, and a fictional RFC with no matching CSD could not stamp anyway. So this company
  is configuration-only; stamping is proven with the demo companies.
- The company is adopted by name (`match`) if a previous run created it without the key.

## Decision 3: CFDI settings of the new company
- Ops: [op_030_mx_company_cfdi_settings]
- Saved like the Settings screen, in the new company's context: fiscal regime `601` (legal entity, general regime),
  PAC `solfact` (Solucion Factible) and `l10n_mx_edi_pac_test_env` on, as the requirement asks until the company has
  its own CSD. No PAC username or password: in test mode Odoo uses the test credentials shipped with the module.

## Decision 4: Customer payments of company 4 post to Outstanding Receipts
- Ops: [op_040_mx_bank_inbound_outstanding]
- With the full Accounting app installed (`account_accountant`, required by `l10n_mx_edi`), a payment on a method
  line without `payment_account_id` creates no journal entry. Without an entry the payment cannot be reconciled with
  the PPD invoice and no payment complement is ever produced. On the template every payment method line of company
  4's bank journal has no account.
- The record is adopted by `match` (journal `account.4_bank`, inbound, code `manual`); the template has exactly one
  such line. The account is company 4's Outstanding Receipts (`account.4_account_journal_payment_debit_account_id`).
- The `account.4_...` xmlids are those of company 4 in this template; the op targets that company only.

## Not covered
- Uploading a CSD and stamping with the new company: needs a CSD issued for its RFC.
- Cancelling CFDI, credit notes, global invoices and the foreign trade complement (`l10n_mx_edi_extended` is not
  installed by this plan).
