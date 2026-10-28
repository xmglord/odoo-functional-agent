# Requirement (verbatim)

No anonymization was needed: "Casa Albar" is a fictional company name and the requirement names no RFC, CURP, bank
or address. In the demo database, Casa Albar is played by the shipped Mexican demo company
`base.demo_company_mx` (id 4), which already has an RFC, regime 601 and a valid demo CSD.

Casa Albar is a Mexican distributor of industrial supplies that sells to companies across Mexico. Its company is already set up in Odoo with its RFC, tax regime and digital seal certificate (CSD); use that company as it is. Invoicing today is done in a separate stamping portal and re-typed into the books. We want every fiscal document issued from Odoo, stamped, and the month-end files for the SAT produced there too.

1. Invoices. Every customer invoice is a stamped CFDI 4.0 that carries the customer's RFC, tax regime, fiscal ZIP code and CFDI use, with 16% IVA. Sales to the general public go out with the generic RFC. If a customer's fiscal data is incomplete, the clerk must find out before stamping, not from a rejection.

2. How customers pay. Counter sales paid at once are invoiced as paid in one installment, with the actual payment way (transfer, card, cash). Customers with 30-day credit are invoiced as paid in installments, and every payment they make, including partial ones, issues its own stamped payment receipt (complemento de pago) for the amount and the remaining balance.

3. Returns and discounts. A return or a discount after invoicing is a stamped credit note (CFDI de egreso) related to the original invoice, never a negative invoice.

4. Mistakes. An invoice issued with wrong data is cancelled with the SAT reason that applies and replaced by a new stamped invoice that references the one it substitutes. The cancelled invoice must stay visible as cancelled, with its reason.

5. Professional fees. Some suppliers are individuals billing professional services (honorarios). Their bills withhold 10% income tax (ISR) and two thirds of the IVA, and the withholdings must show on the bill and in the accounts they will be paid from.

6. Month end. The accountant produces the monthly electronic accounting files for the SAT (chart of accounts with the SAT grouping codes, and the trial balance) from Odoo, without a spreadsheet.
