# Requirement (verbatim)

Vantage Venue Media sells advertising space in third-party venues such as convention centers and stadiums: digital screens, totems, stands, sponsored Wi-Fi and printed media. Each sale is a campaign, and one campaign can include several media, in several venues, for different periods. Today we track campaigns in spreadsheets and the same data is typed again by Sales and Finance. We want our sales cycle in Odoo, from the opportunity to the customer's payment:

1. Opportunities. Sales registers the customer and the opportunity with a short brief: media, venue, start and end dates, and an estimated amount, with documents attached. Customers are classified by type: direct, agency, business partner or corporate. Our pipeline stages are Prospect, Brief Received, Proposal Sent, Negotiation and Won.

2. One campaign code. Each campaign gets a unique code when it is quoted. The same code must appear on the quotation, the sales order and every invoice, so nobody types the customer or the price again after the order is confirmed.

3. Campaign lines. A quotation has one line per medium, venue and period. Example: a 6-month campaign with a digital screen in two venues and a stand in one of them is three lines, each with its own start and end dates. Prices are before VAT, and salespeople can give a discount per line.

4. Quotation history. When a quotation changes before the customer accepts it (price, discount, dates, venues), we need to see what changed, who changed it and when.

5. Invoicing from the order. Finance invoices campaigns in one of three ways, chosen per campaign:
   - 50% down payment when the order is confirmed, and the other 50% before the campaign starts;
   - partial invoices by percentage or by milestone;
   - one full invoice once the customer sends their purchase order.
   The customer's purchase order number must be recorded on the order and shown on the invoices.

6. Balance. At any moment, Sales and Finance must see on the order how much of the campaign has been invoiced and how much is still pending, and on the customer how much they owe us and since when.

## Clarifications (2026-10-27)
- Custom fields (`x_`, Studio-style) are allowed where standard Odoo has no field; each one must be documented so its necessity can be evaluated.
- Line-level quotation history: use standard tracking and document the gap.
- Company: the Mexican demo company (`base.demo_company_mx`), VAT 16%.

## Anonymization
No replacements needed: "Vantage Venue Media" is already fictional and the requirement names no real people, tax ids, banks or addresses. Venue names used in the plan are invented.
