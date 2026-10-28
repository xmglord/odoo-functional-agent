# Requirement (verbatim; no anonymization needed: all names are fictional)

Lumen Ridge Studios is a design and software consultancy. It sells fixed-price projects and monthly retainers to customers at home and abroad, and buys subcontracted work and software subscriptions. Today invoicing is done in a spreadsheet and the accountant rebuilds everything at month end. We want invoicing, payments and the monthly close in Odoo.

1. Taxes and foreign customers. Domestic customers are charged our standard sales tax on services. Customers abroad are not charged tax, and their invoices must say why (export of services). The tax must be applied automatically from the customer, not chosen by hand on each line.

2. Payment terms. Projects are billed 30% when the contract is signed and 70% on delivery, with the delivery invoice due in 30 days. Retainers are due in 15 days. Customers who pay a retainer within 10 days get a 2% discount. When they take it, the tax must be reduced in proportion, not only the total.

3. Foreign currency. European customers are invoiced and pay in euros. When the euro moves between the invoice and the payment, the difference must be booked automatically as an exchange gain or loss, never left as an open balance on the customer.

4. Bank and payments. We have two bank accounts: an operating account in our currency and a euro account. One bank transfer often pays several invoices, and some customers pay part of an invoice. When the accountant matches a bank line, the invoices must close or show the exact amount still owed. A partial refund to a customer is a credit note tied to the original invoice, not a new negative invoice.

5. Profitability per project. Every sales invoice and every vendor bill (subcontractors, software) is assigned to a project and to a department (Design or Engineering). At month end the accountant must see revenue, costs and margin by project and by department without a spreadsheet.

6. Monthly close and roles. The billing clerk creates and sends customer invoices and records vendor bills, but cannot post manual journal entries, change taxes or touch closed periods. Only the accountant posts adjustments and closes the month. Once a month is closed, nobody, including the accountant, can post or change anything dated in it without first reopening it on purpose.

## Clarifications (2026-10-27)
- Projects: one sales order per project; 30% down payment invoice at signature, final invoice deducts it (answer: "Pedido + anticipo").
- Project = analytic account in the existing Project plan; no Project app (answer: "Cuenta analítica").
- Defaults accepted: demo company 1 (USD, generic chart, 15% sales tax) stands in for Lumen Ridge Studios; month close with the Global Lock Date (reopenable), not the Hard Lock Date.
