# Mexican localization (20.0)

What a Mexican company needs on top of standard accounting: the `mx` chart and its taxes (community `l10n_mx`), and
electronic invoicing with CFDI 4.0 (Enterprise `l10n_mx_edi`): fiscal data of the company and its customers, the
codes each CFDI carries, the PAC and CSD that stamp it, payment complements for invoices paid later, and the
foreign trade complement for exports.

Start with the chart entry for a new Mexican company, then the CFDI configuration entry before any invoice.

| Entry | Use it when the requirement mentions |
|---|---|
| [Mexican chart of accounts loaded on company creation](mx_chart_auto_load.md) | a new Mexican company or subsidiary, the SAT chart, MXN, cash-basis journal |
| [IVA 16/8/0/exempt, IEPS and withholdings](iva_and_withholdings.md) | IVA rates, border region 8%, zero-rated or exempt sales, IEPS, retenciones de IVA/ISR, honorarios, arrendamiento |
| [Company and partner fiscal data (RFC, regime, fiscal ZIP)](fiscal_data_rfc_regime.md) | RFC, régimen fiscal, constancia de situación fiscal, público en general, foreign customers, branches |
| [CFDI usage, payment way and payment policy](cfdi_usage_payment_way_policy.md) | uso del CFDI, forma de pago, método de pago, PUE/PPD, UNSPSC product codes, global invoice |
| [CFDI configuration and stamping (PAC, CSD, test mode)](cfdi_configuration_pac_csd.md) | timbrar, PAC, CSD / certificado de sello, test environment, cancelling a CFDI, SAT status |
| [Payment complements for PPD invoices](payment_complements.md) | complemento de pago, REP, partial payments, credit sales, installments |
| [Foreign trade complement (Comercio Exterior)](foreign_trade.md) | exports, Comercio Exterior, fracción arancelaria, Incoterm, pedimento |

## Stamping limits (read before running the stamping scenarios)

- Stamping needs network access to third-party test PACs (Quadrum `finkok` and Solucion Factible `solfact` test
  services). A run without network gets a PAC error, not a pass.
- The demo CSDs expire on 2027-01-18 (company 5, `base.demo_company_2_mx`) and 2027-05-18 (company 4,
  `base.demo_company_mx`). After that date, stamping with that company fails until the template is rebuilt from a
  newer `l10n_mx_edi`.
- Test stamps have no fiscal effect, and their SAT status stays `not_defined`: scenarios assert the PAC stamp
  (`l10n_mx_edi_cfdi_state`, UUID, `l10n_mx_edi.document.state`), never the SAT status.

## Scenarios

Library scenarios in `scenarios/20.0/l10n_mx/`. The fixture plan in `scenarios/20.0/l10n_mx/setup/` (a new MX
company "OFA Demo Mexicana" with its CFDI settings, and an outstanding account on company 4's bank journal) must be
applied first for the two scenarios that say so.

| Scenario | Proves | Network | Needs the setup plan |
|---|---|---|---|
| `l10n_mx_company_chart_autoload` | a company created with country Mexico has the `mx` chart, IVA defaults, MX fiscal positions and the saved CFDI settings; no CSD | no | yes |
| `l10n_mx_vendor_bill_withholdings` | IVA 16% plus the 10.67% IVA and 10% ISR withholdings on a fees bill (community only) | no | no |
| `l10n_mx_invoice_stamp` | a PUE invoice of company 5 stamped by the Solucion Factible test PAC | yes | no |
| `l10n_mx_ppd_payment_complement` | a PPD invoice of company 4 stamped by the Quadrum test PAC, a partial payment reconciled and its payment complement stamped | yes | yes |

## Topics dropped or merged

- None of the suggested topics was dropped. Company and partner fiscal data are one entry (the CFDI reads both
  through the same code). Withholdings are inside the IVA entry because they are taxes of the same chart and are
  applied side by side on the same lines.
- Not covered by an entry yet: down payments and their CFDI relation (`l10n_mx_edi_cfdi_origin` type `07`, payment
  way `30`), credit notes (`01`), global invoices beyond a mention, SAT mass download of received CFDI
  (`l10n_mx_edi.cfdi.request`, needs an `e_firma` certificate), Carta Porte (`l10n_mx_edi_stock`), POS and
  e-commerce CFDI, payroll, and the SAT reports of `l10n_mx_reports` (DIOT, electronic accounting, XML pólizas,
  month-13 trial balance, which in 20.0 are all in `l10n_mx_reports`).

## Cross-references

These entries of other areas carry a `## Mexico notes` section that points to this area in prose. They are not owned
by the l10n_mx task, so the links to the entries here are listed instead:

| Entry | Its Mexico note should link to |
|---|---|
| [accounting/chart_of_accounts.md](../accounting/chart_of_accounts.md) | [mx_chart_auto_load.md](mx_chart_auto_load.md) |
| [accounting/taxes_and_tax_groups.md](../accounting/taxes_and_tax_groups.md) | [iva_and_withholdings.md](iva_and_withholdings.md) |
| [accounting/fiscal_positions.md](../accounting/fiscal_positions.md) | [iva_and_withholdings.md](iva_and_withholdings.md), [foreign_trade.md](foreign_trade.md) |
| [accounting/payment_terms.md](../accounting/payment_terms.md) | [cfdi_usage_payment_way_policy.md](cfdi_usage_payment_way_policy.md) (PPD rule: due date in a later month or several term lines) |
| [accounting/payments_and_reconciliation.md](../accounting/payments_and_reconciliation.md) | [payment_complements.md](payment_complements.md) (verified live: the complement is stamped from the invoice's Update Payments) |
| [accounting/invoicing_vs_accounting_apps.md](../accounting/invoicing_vs_accounting_apps.md) | [cfdi_configuration_pac_csd.md](cfdi_configuration_pac_csd.md) (`l10n_mx_edi` depends on `account_accountant`) |
| [accounting/multi_currency.md](../accounting/multi_currency.md) | [foreign_trade.md](foreign_trade.md) (USD rate needed by the complement) |
| [accounting/journals.md](../accounting/journals.md) | none yet: series and folio per journal are not covered here |
| [accounting/lock_dates.md](../accounting/lock_dates.md) | [cfdi_configuration_pac_csd.md](cfdi_configuration_pac_csd.md) |
| [sales_crm/invoicing_policy.md](../sales_crm/invoicing_policy.md) | [cfdi_usage_payment_way_policy.md](cfdi_usage_payment_way_policy.md) (sales order CFDI fields of `l10n_mx_edi_sale`) |
| [sales_crm/payment_terms_on_quotes.md](../sales_crm/payment_terms_on_quotes.md) | [cfdi_usage_payment_way_policy.md](cfdi_usage_payment_way_policy.md) |
| [sales_crm/down_payments.md](../sales_crm/down_payments.md) | none yet: down payment CFDI not covered here |
| [multi_company/companies_and_branches.md](../multi_company/companies_and_branches.md) | [fiscal_data_rfc_regime.md](fiscal_data_rfc_regime.md), [cfdi_configuration_pac_csd.md](cfdi_configuration_pac_csd.md) (branches stamp with the root company's RFC and CSD) |
| [purchase_inventory/bill_control.md](../purchase_inventory/bill_control.md) | [iva_and_withholdings.md](iva_and_withholdings.md) (withholdings on vendor bills) |

## Upkeep log

| Entry | Agent time: tokens | Agent time: minutes | Author review (min) |
|---|---|---|---|
| mx_chart_auto_load.md | | | |
| iva_and_withholdings.md | | | |
| fiscal_data_rfc_regime.md | | | |
| cfdi_usage_payment_way_policy.md | | | |
| cfdi_configuration_pac_csd.md | | | |
| payment_complements.md | | | |
| foreign_trade.md | | | |
| overhead | | | |

Agent time is measured from the authoring agent's session transcript, between markers it printed before and after
each entry. `cfdi_configuration_pac_csd.md` was edited once more after its end marker, inside a second marker pair.
Overhead is the shared research before the first entry plus the index, the fixture plan and the scenarios. Author
review is minutes the author spent checking the entry.
