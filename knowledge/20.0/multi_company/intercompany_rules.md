---
title: Inter-company rules (mirror orders and invoices between companies)
area: multi_company
odoo_version: 20.0
edition: enterprise
source: [enterprise/account_inter_company_rules/models/res_company.py@20.0, enterprise/account_inter_company_rules/models/account_move.py@20.0, enterprise/sale_purchase_inter_company_rules/__manifest__.py@20.0, enterprise/sale_purchase_inter_company_rules/models/res_company.py@20.0, enterprise/sale_purchase_inter_company_rules/models/purchase_order.py@20.0, enterprise/sale_purchase_inter_company_rules/models/sale_order.py@20.0, enterprise/sale_purchase_stock_inter_company_rules/models/res_company.py@20.0, enterprise/sale_purchase_stock_inter_company_rules/models/purchase_order.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [account_inter_company_rules, sale_purchase_inter_company_rules, sale_purchase_stock_inter_company_rules]
models: [res.company, res.config.settings, purchase.order, sale.order, account.move]
settings: [intercompany_generate_sales_orders, intercompany_generate_purchase_orders, intercompany_generate_bills_refund, intercompany_document_state, intercompany_purchase_journal_id, intercompany_sync_delivery_receipt]
---

## When to use
- If companies of the same database buy from and sell to each other (a distribution subsidiary buys from the
  manufacturing company), and each side would otherwise type the mirror document by hand, turn on the inter-company
  rules: a document confirmed in one company creates its counterpart in the other.
- If only invoices cross (management fees, recharges between entities), the invoice rule alone is enough.

## Configuration
- Modules (Enterprise):
  - `account_inter_company_rules`: invoices and credit notes → vendor bills and refunds.
  - `sale_purchase_inter_company_rules` (depends on `sale_management`, `purchase`, `account_inter_company_rules`;
    auto-installs when they are present): purchase orders ↔ sales orders.
  - `sale_purchase_stock_inter_company_rules` (auto-installs with `sale_stock`, `purchase_stock` and the module
    above): picks the warehouse and links the delivery with the receipt.
  - There is no `inter_company_rules` module in 20.0.
- Settings, all **per company** (related to `res.company`, so a `set_settings` op with that company's `company`):
  - `intercompany_generate_sales_orders`: when **another** company confirms a purchase order whose vendor is this
    company, create a sales order in this company.
  - `intercompany_generate_purchase_orders`: when another company confirms a sales order whose customer is this
    company, create a purchase order in this company.
  - `intercompany_generate_bills_refund`: when another company posts a customer invoice or credit note to this
    company, create a vendor bill or refund in this company, in `intercompany_purchase_journal_id` (defaults to its
    first purchase journal).
  - `intercompany_document_state`: `draft` (default) or `posted` ("Validated"): leave the generated document in
    draft, or confirm/post it.
  - `intercompany_sync_delivery_receipt` (stock module, default true): link the delivery and the receipt.
- The rule is set on the **receiving** company. The company is recognised from the document's partner:
  `_find_company_from_partner` looks for the company whose `partner_id` is the partner or its parent.
- What is generated (live, PO → SO): the sales order gets `company_id` = the vendor company, `partner_id` = the
  buying company's partner (from its warehouse), `auto_generated = true`, `auto_purchase_order_id` = the PO,
  `client_order_ref` = the PO name, the PO's lines, prices and quantities, and the taxes of its own company; the PO
  gets `partner_ref` = the SO name. The PO's `auto_sale_order_id` stays empty (it is set only on POs generated from
  an SO).
- Generated documents are created as the superuser (`SUPERUSER_ID`), not as a configured user.

## How to verify
- Settings: read `intercompany_generate_sales_orders` (etc.) on the receiving `res.company`.
- Flow (scenario `multi_company_intercompany_so_po`): confirm a PO in company A with company B's partner as vendor;
  `sale.order` search `[["auto_purchase_order_id", "=", <po>]]` finds one order with `company_id` = B,
  `auto_generated = true`, `state = 'draft'`; the PO's `partner_ref` is that order's name.
- Invoices: `account.move` search `[["auto_invoice_id", "=", <invoice>]]` in the receiving company.

## Pitfalls
- **20.0 drift: no inter-company user.** 19.0 had `res.company.intercompany_user_id` (and a required settings
  field) and created the documents as that user; 20.0 removed it and always uses the superuser. Plans must not set
  it. 20.0 also dropped `intercompany_warehouse_id` and `intercompany_receipt_type_id`: the warehouse is the one
  whose partner matches the delivery address, else the company's first warehouse.
- The receiving company needs a `stock.warehouse` when the stock module is installed, otherwise the confirm fails
  with `UserError` "Configure correct warehouse for company(...)". A new company has none (see
  [companies_and_branches.md](companies_and_branches.md)).
- The SO's currency comes from the buying company partner's pricelist in the receiving company; if that pricelist's
  currency differs from the PO's, the confirm fails ("You cannot create SO from PO because sale price list currency
  is different than purchase price list currency.").
- Products on the PO must be usable in the receiving company: use shared products (`company_id` empty) for
  inter-company trade. A product restricted to the buying company would break the company check on the generated
  SO lines (source reasoning; not tested live).
- The rule never triggers on a document that was itself generated (`auto_generated`), so there are no loops; it
  also does not trigger when the partner is not a company's partner.
- Lines added later to a PO that already generated an SO are copied to that SO (`purchase.order.write`); cancelling the PO
  only posts a note on the SO, it does not cancel it.

## Alternatives
- Manual mirror documents when the volume is low or each side negotiates its own terms.
- Branches instead of companies when the units are one legal entity: no inter-company documents are needed (see
  [companies_and_branches.md](companies_and_branches.md)).
- Resupply between warehouses of one company (stock routes) when the units are one company.
