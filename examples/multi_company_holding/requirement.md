# Requirement (verbatim)

Ridgeline is a small US group. Ridgeline Holdings owns two operating companies: Ridgeline Foods, a food distributor, and Ridgeline Logistics, a trucking company. Ridgeline Foods also runs a second branch in another city that shares its tax ID and books but has its own warehouse and staff. Each company files its own taxes and has its own bank accounts. Today every company runs separate software and the group controller merges spreadsheets every month. We want the whole group in one Odoo database.

1. Structure. Holdings, Foods and Logistics are separate legal companies, each with its own chart of accounts, journals, bank accounts and document numbering. The Foods branch is not a separate legal company: its invoices carry Foods' tax ID, but they must be identifiable as the branch's, and its stock is kept apart from the main warehouse.

2. Shared and separate data. Products and customers are shared across the group, so nobody creates the same customer twice. Vendors are shared too, but each company negotiates its own payment terms with them. Prices, taxes and accounting settings are per company.

3. Who sees what. Staff of each company work only in their company: they must not see or change another company's invoices, orders, stock or bank. Branch staff work only in the branch. The group controller sees every company, can switch between them and can run reports for several at once, but does not post entries in Logistics, which has its own accountant.

4. Trucking between companies. Logistics hauls goods for Foods. When Foods confirms a purchase order to Logistics for a haul, Logistics must get the matching sales order without anyone re-typing it. When Logistics invoices Foods, Foods gets the vendor bill automatically, as a draft for its accountant to check.

5. Management fee. Every month Holdings invoices each operating company a fixed management fee for shared services, and each company receives the matching bill the same way as in need 4.

6. Group reporting. The controller needs a profit and loss and a balance sheet for each company and for the whole group. The group figures must not count twice what the companies sell to each other (the hauls and the management fees).

# Clarifications agreed with the user

- Group controller: Bookkeeper with access to every company; a restriction stops them creating, changing or deleting
  journal entries outside an allow-list of companies (Holdings, Foods, the Foods branch, Eliminations), so Logistics
  is excluded and the restriction fails closed if a company is renamed or added.
- Eliminations: a fourth company, Ridgeline Eliminations, holds the monthly elimination entries; group figures are
  the report run with every company selected.

# Anonymization

The group and its companies are already fictional. Added fictional data: the branch city "Riverside", tax IDs
00-0000101 (Holdings), 00-0000102 (Foods and its branch), 00-0000103 (Logistics), and the sample partners and
products named in plan.md. No real data was replaced.
