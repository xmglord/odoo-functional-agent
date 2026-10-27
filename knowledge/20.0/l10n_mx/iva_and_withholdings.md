---
title: IVA 16/8/0/exempt, IEPS and withholdings in the mx chart
area: l10n_mx
odoo_version: 20.0
edition: community
source: [odoo/addons/l10n_mx/data/template/account.tax-mx.csv@20.0, odoo/addons/l10n_mx/data/template/account.tax.group-mx.csv@20.0, odoo/addons/l10n_mx/data/template/account.fiscal.position-mx.csv@20.0, odoo/addons/l10n_mx/models/account_tax.py@20.0, odoo/addons/l10n_mx/models/template_mx.py@20.0, enterprise/l10n_mx_edi/data/template/account.tax-mx.csv@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [l10n_mx]
models: [account.tax, account.tax.group, account.fiscal.position, account.move, account.move.line]
settings: [sale_tax_id, purchase_tax_id, tax_exigibility]
---

## When to use
- Every Mexican company charges IVA. Pick the tax the chart already has instead of creating one:
  - general rate: IVA 16% (`tax12` sales, `tax14` purchases), the company default;
  - northern and southern border region incentive: IVA 8% (`tax17` sales, `tax16` purchases, `tax23` "8% S.");
  - zero-rated goods (basic food, medicines) and exports: IVA 0% (`tax9` sales, `tax13` purchases);
  - exempt activities (some education, housing rent, medical services): "Exento" (`tax19` sales, `tax20` purchases).
    0% and exempt both add no tax, but the CFDI reports them differently (`TipoFactor` `Tasa` with rate 0 versus
    `Exento`), and only 0% lets the issuer credit its input IVA, so the choice is a fiscal one, not cosmetic.
- If the company pays a natural person for professional fees or rent, it must withhold part of the IVA and ISR:
  add the withholding taxes to the bill line next to IVA 16% (`tax8` "10.67% WH" = two thirds of IVA on fees,
  `tax7` "10.67% WH L" on financial leasing, `tax2` "10% WH L" IVA on rent, `tax1` "4% WH" IVA on freight, `tax5`
  "10% WH I S" ISR, `tax3` "10% WH L I" ISR on rent, `mx_wh_1_25` 1.25% ISR to RESICO taxpayers).
- If the company sells goods subject to IEPS (alcohol, tobacco, sugary drinks, fuels), activate the IEPS sales tax of
  the right rate (8, 25, 26.5, 30, 53%); they ship inactive.

## Configuration
- Taxes are created by the `mx` chart per company as `account.<company_id>_<id>` (live, company 4:
  `account.4_tax12`, `account.4_tax14`, `account.4_tax8`, `account.4_tax5`, ...).
- `account.tax` fields added by `l10n_mx` (`odoo/addons/l10n_mx/models/account_tax.py@20.0`):
  - `l10n_mx_tax_type`: `isr`, `iva`, `ieps`, `local` (stored compute, `iva` by default for Mexican taxes, editable);
  - `l10n_mx_factor_type`: `Tasa`, `Cuota`, `Exento` (CFDI `TipoFactor`).
- Withholdings are taxes with a negative `amount` (`-10.666666666667`, `-10`, `-4`, `-1.25`) and `type_tax_use =
  'purchase'`; only the RESICO 1.25% withholding has a sales twin (`mx_wh_1_25_sale`), inactive.
- Cash basis: the IVA taxes and IEPS have `tax_exigibility = 'on_payment'` (IVA is due when paid in Mexico), with
  `cash_basis_transition_account_id` set; the template switches on the company's `tax_exigibility` and sets
  `tax_cash_basis_journal_id` to the `CBMX` journal. Exempt and ISR withholdings are `on_invoice`.
- Tax groups (`account.tax.group-mx.csv`): `tax_group_iva_16`, `tax_group_iva_8`, `tax_group_iva_0`,
  `tax_group_exe_0`, `tax_group_iva_ret_4`, `tax_group_iva_ret_10`, `tax_group_iva_ret_1067`,
  `tax_group_isr_ret_10`, `tax_group_iva_isr_ret_1_25`, `tax_group_ieps_*`.
- Fiscal positions, mapping on the tax (20.0): IVA 16%/8% and Exento belong to "MX Domestic"; the 0% taxes belong to
  "Foreign Customer" and replace (`original_tax_ids`) 16% and 8%; "Freight", "Honorarium" and "Lease" carry
  purchase taxes `vat16_T`, `vat16_2_3_H`, `vat16_2_3_L` that replace purchase IVA 16%.
- With `l10n_mx_edi`, a "Local Tax" pair (`l10n_mx_edi_tax_local_sale` / `_purchase`, `l10n_mx_tax_type =
  'local'`) is added for state taxes reported in the CFDI local taxes complement.

## How to verify
- Company defaults: `res.company.account_sale_tax_id` is the 16% sales tax and `account_purchase_tax_id` the 16%
  purchase tax (live, companies 4 and the fixture's new company).
- On a tax: `amount`, `type_tax_use`, `l10n_mx_tax_type`, `l10n_mx_factor_type`, `tax_exigibility`, `active`.
- On a bill: base 10,000.00 with `tax14` + `tax8` + `tax5` gives `amount_tax = -466.67` and `amount_total =
  9,533.33`, with one tax line per withholding (`tax_line_id`, `balance` -1,066.67 and -1,000.00). Scenario
  `scenarios/20.0/l10n_mx/l10n_mx_vendor_bill_withholdings.json` checks this live.

## Pitfalls
- Two taxes are named "16%" (sales and purchase) and two "8%", "0%", "Exento": search by `name` plus
  `type_tax_use` and `company_id`, never by name alone.
- Sales IEPS taxes, the RESICO 1.25% withholdings are inactive (`active = False`) on a new company; search with
  `active in [true, false]` before deciding they are missing.
- Because IVA is on payment, a posted invoice books IVA to a transition account; the tax only moves to the payable
  IVA account when the invoice is paid (entry in the `CBMX` journal). Tax reports before payment look "empty".
- "10% WH I S" is described in the chart as ISR withholding "on salaries"; it is the 10% ISR rate used on
  professional fees too. Check the description with the accountant before labelling bills.
- The sales 0% tax is in the "Foreign Customer" position: an export customer with that position gets 0% instead of
  16% automatically, but a domestic zero-rated product needs the 0% tax set on the product itself.

## Alternatives
- Fiscal positions instead of per-product taxes when a whole customer or vendor class changes the tax ("Foreign
  Customer", "Honorarium", "Lease", "Freight").
- A border-region company can set IVA 8% as its default sales tax (`sale_tax_id` setting) instead of changing
  products.

## Mexico notes
This entry is the Mexico note for [taxes_and_tax_groups.md](../accounting/taxes_and_tax_groups.md) and
[fiscal_positions.md](../accounting/fiscal_positions.md). How these taxes reach the CFDI: [cfdi_usage_payment_way_policy.md](cfdi_usage_payment_way_policy.md).
