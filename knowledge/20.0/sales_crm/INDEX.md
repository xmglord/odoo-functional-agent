# Sales and CRM (20.0)

Everything that happens before a customer invoice is posted: leads and opportunities, sales teams, quotations and
sales orders, prices and discounts, and how orders turn into invoices. Accounting objects that sales documents only
reference (payment terms, taxes) are described here only as far as sales uses them; see the accounting area for the
rest.

| Entry | Use it when the requirement mentions |
|---|---|
| [Leads, opportunities and pipeline stages](leads_opportunities_pipeline.md) | qualifying requests, lead conversion, pipeline steps, won/lost |
| [Sales teams and team membership](sales_teams.md) | teams, team leaders, salespeople in several teams, lead assignment |
| [Quotation templates and optional lines](quotation_templates.md) | standard offers, packages, optional extras on the online quotation |
| [Pricelists and customer-specific prices](pricelists.md) | customer prices, volume breaks, promotions by date, other currencies |
| [Discounts on sales order lines and global discounts](discounts.md) | per-line discounts, a discount on the whole order |
| [Invoicing policy (ordered vs delivered quantities)](invoicing_policy.md) | invoice on order vs on delivery, automatic invoicing |
| [Down payments on sales orders](down_payments.md) | advances, deposits, partial invoices before delivery |
| [Online signature, online payment and quotation validity](online_signature_payment.md) | customer accepts or pays the quotation online, prepayment, expiry |
| [Payment terms on quotations and sales orders](payment_terms_on_quotes.md) | credit conditions, installments, early payment discount |

Scenarios for this area live in `scenarios/20.0/sales_crm/`: `sales_quote_to_invoice` (quote, confirm, deliver,
invoice, post) and `crm_lead_to_quote` (lead, opportunity, quotation, order, won).

## Upkeep log

| Entry | Agent time: tokens | Agent time: minutes |
|---|---|---|
| leads_opportunities_pipeline.md | 12,473 | 1.3 |
| sales_teams.md | 14,653 | 1.2 |
| quotation_templates.md | 10,335 | 1.5 |
| pricelists.md | 16,443 | 1.4 |
| discounts.md | 10,585 | 0.9 |
| invoicing_policy.md | 12,019 | 0.9 |
| down_payments.md | 8,006 | 0.7 |
| online_signature_payment.md | 9,800 | 0.9 |
| payment_terms_on_quotes.md | 8,980 | 0.8 |
| overhead | 177,075 | 6.6 |

Agent time is measured from the authoring agent's session transcript, between markers it printed before and after each entry. Tokens are the new tokens of its API calls in that window (input, cache writes and output); re-reads of already cached context are excluded, because every call re-reads the whole conversation (15.0 M such tokens over the session, 98% of the raw total). Overhead is the shared research before the first entry plus the index and the scenarios.
