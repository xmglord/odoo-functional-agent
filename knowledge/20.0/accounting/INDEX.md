# Accounting (20.0)

Everything from the chart of accounts to a paid invoice: which accounting app is installed, the chart and its taxes,
fiscal positions, journals, payment terms, payments and reconciliation, foreign currencies, closing periods with lock
dates, and analytic accounting. How sales documents pick up payment terms and taxes is in the sales area; Mexican
taxes, CFDI and SAT reporting are in the `l10n_mx` area.

Start with the apps entry: in 20.0 the full Accounting app is the Enterprise module `accountant`, and whether it is
installed changes payment results and user rights.

| Entry | Use it when the requirement mentions |
|---|---|
| [Invoicing vs Accounting apps (modules and access groups)](invoicing_vs_accounting_apps.md) | "Accounting" vs "Invoicing", bookkeepers, bank reconciliation, reports, accounting rights |
| [Chart of accounts per country (chart templates)](chart_of_accounts.md) | a new company, a country's chart, account numbers, changing the chart |
| [Taxes and tax groups](taxes_and_tax_groups.md) | VAT/sales tax rates, default taxes, tax-included prices, cash-basis taxes, tax subtotals |
| [Fiscal positions and the 20.0 tax-side mapping](fiscal_positions.md) | exports at 0%, tax-exempt customers, taxes by country or state, swapping accounts |
| [Journals (sales, purchase, bank, cash, miscellaneous)](journals.md) | separate numbering, several bank accounts, credit note sequence, hashing |
| [Payment terms, due dates and installments](payment_terms.md) | credit days, end of month, installments, early payment discount, due dates |
| [Payments and reconciliation basics](payments_and_reconciliation.md) | registering payments, partial payments, outstanding credits, outstanding accounts |
| [Multi-currency (rates, foreign-currency documents, exchange differences)](multi_currency.md) | foreign currencies, exchange rates, automatic rates, exchange gain/loss |
| [Lock dates (closing periods)](lock_dates.md) | closing a month or year, tax return filed, locking sales or purchases, exceptions |
| [Analytic accounting (plans, accounts, distributions)](analytic_accounting.md) | cost centers, departments, projects, profitability per dimension, mandatory analytic |

Scenarios for this area live in `scenarios/20.0/accounting/`: `accounting_invoice_payment_reconcile` (invoice with a
30-day term, full payment through the register-payment wizard, partial payment reconciled by hand) and
`accounting_fiscal_position_export` (domestic 15% tax mapped to 0% for an export customer, checked on the invoice
lines' `tax_ids`). Both need the fixture plan in `scenarios/20.0/accounting/setup/` applied first.

## Upkeep log

| Entry | Agent time: tokens | Agent time: minutes |
|---|---|---|
| chart_of_accounts.md | 8,228 | 0.7 |
| taxes_and_tax_groups.md | 12,567 | 0.9 |
| fiscal_positions.md | 8,193 | 0.6 |
| payment_terms.md | 9,215 | 0.6 |
| journals.md | 11,167 | 0.9 |
| payments_and_reconciliation.md | 9,668 | 0.7 |
| multi_currency.md | 10,446 | 0.8 |
| lock_dates.md | 5,784 | 0.4 |
| analytic_accounting.md | 10,017 | 0.9 |
| invoicing_vs_accounting_apps.md | 10,630 | 1.1 |
| overhead | 274,123 | 14.6 |

Agent time is measured from the authoring agent's session transcript, between markers it printed before and after each entry. Tokens are the new tokens of its API calls in that window (input, cache writes and output); re-reads of already cached context are excluded, because every call re-reads the whole conversation (25.8 M such tokens over the session, 99% of the raw total). Three entries (payment terms, payments and reconciliation, fiscal positions) were edited again after their end markers to add values the scenarios read live; that time is in overhead. Overhead is the shared research before the first entry plus the index and the scenarios.
