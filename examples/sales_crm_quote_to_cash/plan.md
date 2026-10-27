# Vantage Venue Media: campaign sales cycle from opportunity to payment

- Requirement: [requirement.md](requirement.md)
- Target edition: enterprise
- Areas: sales_crm, accounting, l10n_mx
- Company: the Mexican demo company `base.demo_company_mx` (MXN, VAT 16% `account.4_tax12`)

## Summary
Vantage sells advertising campaigns. The plan runs the whole cycle on standard CRM → Sales → Invoicing:
- An opportunity holds the brief in team lead properties.
- The quotation number is the campaign code, and it flows unchanged to the order and every invoice.
- Each campaign line is a medium (a service product) in a venue (a no-variant attribute).
- Finance invoices from the order with the down-payment wizard.

Standard Odoo has no field for three things, so the plan adds four custom `x_` fields, each documented below so you
can decide whether it is worth keeping: line start/end dates, customer type and billing method. Line-level history
of quotation changes stays a documented gap.

## Decision 1: Apps
- Ops: [op_010_install_apps]
- Decision: rely on `sale_management`, `crm`, `sale_crm` (opportunity → quotation link) and `account_followup`
  (customer balance and overdue follow-up, Enterprise).
- Business reason: the cycle goes opportunity → quotation → order → invoice → payment, with the customer balance.
- Pre-state: all four are already installed in the template, so this op reports `unchanged` (`pre_state`) and
  proves nothing; it is kept so the plan states its dependencies.
- Sources: `knowledge/20.0/sales_crm/leads_opportunities_pipeline.md`, `knowledge/20.0/accounting/payment_terms.md`

## Decision 2: Per-line discount and down payment account
- Ops: [op_020_sales_settings]
- Decision: enable Discounts (`group_discount_per_so_line`), keep Variants (`group_product_variant`) on so products
  can carry the Venue attribute, and book down payments on "Domestic customer advance" (`account.4_cuenta206_01`,
  type `liability_current`) through `downpayment_account_id`.
- Business reason: salespeople give a discount per line (req. 3). The 50% advance is a debt to the customer until
  the campaign runs, not income (req. 5).
- What Odoo does: `sale.order.line.discount` (0-100) becomes visible; `res.company.downpayment_account_id` is
  used on down payment invoice lines instead of the income account.
- Menu: Sales > Configuration > Settings > Pricing > Discounts; Sales > Configuration > Settings > Invoicing >
  Down Payments.
- Pre-state: Variants already on, Discounts off and no down payment account, so the op will be `updated`.
- Pitfalls: the line `discount` is 0-100 while the global-discount wizard's `discount_percentage` is 0-1. Only
  posted down payments are deducted from the final invoice.
- Sources: `knowledge/20.0/sales_crm/discounts.md`, `knowledge/20.0/sales_crm/down_payments.md`

## Decision 3: Campaign code = quotation number
- Ops: [op_030_campaign_sequence]
- Decision: a company-specific `ir.sequence` with code `sale.order` and prefix `CMP/%(year)s/` (4 digits) for the
  Mexican company. Quotations there are numbered `CMP/2026/0001`, `CMP/2026/0002`, ...
- Business reason: req. 2. The number is assigned when the quotation is created and stays the same after
  confirmation, so the quotation and the order share one code.
- What Odoo does: `sale.order.create` calls `next_by_code('sale.order')` with the order's company, and
  `ir.sequence.next_by_code` prefers the company's own sequence over the shared one (`sale.seq_sale_order`, prefix
  `S`). Each invoice made from the order gets `account.move.invoice_origin` = the campaign code. The invoice PDF
  prints it as "Source". The customer never has to be retyped: the invoice wizard copies partner, lines, prices,
  discounts and taxes from the order.
- Pre-state: no company-specific sequence exists; created.
- Alternatives: change the prefix of the shared `sale.seq_sale_order` (affects every company); or add an `x_` code
  field (rejected: the order number already is unique and already flows to invoices).
- Pitfalls: the code is on the invoice as origin, not as the invoice number. Invoice numbers keep the journal's
  sequence (fiscal folio in Mexico).
- Sources: Uncited: no compendium entry; names checked with `ofa inspect --target t21 ir.sequence --fields
  code,prefix,company_id` and the 20.0 source (`odoo/addons/sale/models/sale_order.py`,
  `odoo/odoo/addons/base/models/ir_sequence.py`).

## Decision 4: Opportunity brief and pipeline
- Ops: [op_040_campaign_team] [op_050_stage_prospect] [op_060_stage_brief] [op_070_stage_proposal]
  [op_080_stage_negotiation] [op_090_stage_won]
- Decision:
  - A "Campaign Sales" team (`crm.team`, Mexican company, opportunities only, Leads off). Its lead properties
    (`crm.team.lead_properties_definition`) hold the brief: Media (tags: digital screen, totem, stand, sponsored
    Wi-Fi, printed media), Venues (text), Campaign start and Campaign end (dates).
  - The estimated amount is the standard `crm.lead.expected_revenue`. Documents are chatter attachments.
  - Pipeline stages (`crm.stage`): the default New/Qualified/Proposition are renamed to Prospect/Brief
    Received/Proposal Sent, Negotiation is added at sequence 4, and Won (`is_won`) is kept.
- Business reason: req. 1. Properties are standard, no-code fields defined per team, so the brief needs no custom
  field.
- What Odoo does: `crm.lead.lead_properties` shows the team's properties on the opportunity form. The "New
  Quotation" button (`sale_crm`) creates a `sale.order` with `opportunity_id` and the customer prefilled.
- Pre-state: the stages exist with other names (the ops report `adopted`). Negotiation and the team are created.
- Alternatives: per-team stages (`crm.stage.team_ids`) if other teams keep a different pipeline. Here there is one
  sales process, so the shared stages are renamed.
- Pitfalls: brief properties do not carry over to the quotation. Sales enters lines, venues and dates there,
  because the quotation is the binding document. Lost opportunities are archived.
- Sources: `knowledge/20.0/sales_crm/leads_opportunities_pipeline.md`, `knowledge/20.0/sales_crm/sales_teams.md`

## Decision 5: Customer type (custom field)
- Ops: [op_100_field_customer_type] [op_100_field_customer_type_opt_direct]
  [op_100_field_customer_type_opt_agency] [op_100_field_customer_type_opt_business_partner]
  [op_100_field_customer_type_opt_corporate] [op_110_view_partner_type]
- Decision: custom selection field `res.partner.x_customer_type` (Direct, Agency, Business partner, Corporate),
  shown after Tags on the contact form (view extension of `base.view_partner_form`).
- Business reason: req. 1. The four types are mutually exclusive, and reports should group by them.
- Sources: Uncited: no compendium entry; names checked with `ofa inspect --target t21 ir.model.fields --fields
  name,model_id,ttype,state,tracking` and `ofa inspect --target t21 ir.model.fields.selection`.

## Decision 6: Campaign lines
- Ops: [op_160_attr_venue] [op_161_venue_bay] [op_162_venue_ridge] [op_163_venue_north] [op_170_prod_screen]
  [op_171_prod_totem] [op_172_prod_stand] [op_173_prod_wifi] [op_174_prod_printed] [op_180_venues_digital_screen]
  [op_181_venues_totem] [op_182_venues_stand] [op_183_venues_sponsored_wifi] [op_184_venues_printed_media]
  [op_130_field_line_start] [op_131_field_line_end]
- Decision:
  - **Medium:** each medium is a service product (`product.template`, `type = 'service'`,
    `invoice_policy = 'order'`, VAT 16% excluded, Mexican company). The list price is a fictional reference price per
    period.
  - **Venue:** a `product.attribute` "Venue" with `create_variant = 'no_variant'` and three fictional venues. One
    product has no variants per venue: the venue is picked on the line (`product_no_variant_attribute_value_ids`)
    and is written into the line description, which flows to the invoice line.
  - **Period:** each line gets custom fields `sale.order.line.x_start_date` and `x_end_date`, shown in the order
    lines list before the discount.
- Business reason: req. 3, one line per medium, venue and period. The six-month example is three lines:
  - Digital Screen in Blue Bay Convention Center;
  - Digital Screen in Green Ridge Stadium;
  - Stand in Blue Bay Convention Center.
  Each line has its own dates, a price before VAT and its own discount.
- Pre-state: none of these records exist; created.
- Alternatives:
  - **Venue:** real variants (one per venue) only if prices or stock differ by venue. An analytic plan per venue if
    Finance wants profitability per venue.
  - **Period:** write the period in the line description. This is standard and flows to the invoice, but it is
    free text, so it cannot be filtered or validated.
  - `sale_subscription`/`sale_renting` were rejected: their dates are per order, not per line.
- Pitfalls: the `x_` dates do not flow to invoice lines (there is no standard mapping). The venue does, through the
  description. The `no_variant` attribute must keep at least one value per product.
- Sources: `knowledge/20.0/sales_crm/invoicing_policy.md`, `knowledge/20.0/accounting/taxes_and_tax_groups.md`;
  attribute and custom-field names are uncited (no compendium entry) and were checked with `ofa inspect --target
  t21 product.attribute --fields create_variant,display_type` and `ofa inspect --target t21 sale.order.line
  --all-fields` (no standard date field on the line).

## Decision 7: Billing method per campaign and balances on the order
- Ops: [op_120_field_billing_method] [op_120_field_billing_method_opt_down_payment_50]
  [op_120_field_billing_method_opt_partial] [op_120_field_billing_method_opt_full_on_po] [op_140_view_order_form]
  [op_150_view_order_list]
- Decision:
  - **Billing method:** custom selection `sale.order.x_billing_method`, tracked in the chatter (`tracking = 10`).
    Options: 50% down payment + 50% before start, partial invoices (percentage or milestone), full invoice on
    customer PO.
  - **Balances on the form:** the order form shows it after the payment terms, together with the standard
    `sale.order.amount_invoiced` ("Already invoiced") and `sale.order.amount_unpaid` ("Amount Remaining") once
    confirmed. `amount_unpaid` = `amount_total` minus everything invoiced from the order (draft or posted, VAT
    included), minus online payments, so it drops by the down payments. It is stored.
  - **Why not "Un-invoiced Balance":** the first apply showed `sale.order.amount_to_invoice` with this label, and
    the tests showed it does not fit. It is computed per line as ordered quantity minus posted invoiced quantity,
    and down payment lines have quantity 0, so after a 50% down payment it still shows 100%. Measured on t21:
    CMP/2026/0001 had total 133,980, invoiced 66,990, `amount_to_invoice` 133,980 and `amount_unpaid` 66,990.
  - **Balances in the list:** the quotation/order list (extension of `sale.sale_order_tree`) shows both amounts,
    with totals.
- How each method runs, all from the order's "Create Invoice" wizard `sale.advance.payment.inv`:
  - 50/50: on confirmation, `advance_payment_method = 'percentage'` with `amount = 50` and post the result. Before
    the start date, run a regular invoice (`delivered`) with `deduct_down_payments`: it bills 100% minus the posted
    50%.
  - Partial by percentage or milestone: one down payment per milestone, `percentage` or `fixed` (`fixed_amount`).
    The last invoice is the regular one, which deducts all of them.
  - Full on PO: record the PO number in `sale.order.client_order_ref` ("Customer Reference"), then a regular
    invoice for 100%.
- Customer PO number (req. 5): `client_order_ref` is standard. Every invoice from the order gets `account.move.ref` =
  `client_order_ref`, printed as "Reference" on the invoice PDF, next to "Source" = campaign code. No custom field
  needed.
- Pre-state: nothing exists; created.
- Alternatives:
  - **Billing method:** an order tag (`sale.order.tag_ids`) is standard but not exclusive and not tracked. Or no
    field at all, because Odoo does not need to know the method to invoice. The field only documents the agreement
    and lets Finance filter.
  - **Milestones:** `sale_project` milestones (services invoiced on reached milestones) were rejected: they need the
    Project app for every campaign.
- Pitfalls:
  - The billing method does not drive anything automatically. Nothing blocks a full invoice on a 50/50 campaign,
    and nothing reminds Finance before the start date; that would need an automation rule.
  - `amount_unpaid` counts draft invoices as invoiced, while `amount_invoiced` counts only posted ones. While an
    invoice is still a draft, Already invoiced + Amount Remaining is less than the total. Once it is posted, the two
    add up to the total.
  - `amount_unpaid` also subtracts online payment transactions (`amount_paid`). There are none in this flow; if
    portal payment is switched on, a paid but uninvoiced amount also lowers it.
  - The view `arch` is compared literally on re-apply; if Odoo reformats it, apply fails with `VALUE_NOT_HELD`.
- Mexico: a 50% down payment is normally its own CFDI, related to the final invoice (CFDI relation 07; from general SAT knowledge, uncited). This plan
  does not configure that; see the l10n_mx area.
- Sources: `knowledge/20.0/sales_crm/down_payments.md`, `knowledge/20.0/sales_crm/invoicing_policy.md`; field
  names checked with `ofa inspect --target t21 sale.order --fields client_order_ref,amount_invoiced,amount_to_invoice`
  and the 20.0 source (`sale_order.py` `_prepare_invoice`: `ref`, `invoice_origin`).

## Decision 8: Customer balance (no configuration)
- Ops: none (standard).
- Decision: Finance reads what the customer owes and since when from standard Enterprise accounting:
  - `res.partner.total_due` and `total_overdue` on the customer's follow-up (`account_followup`);
  - the Aged Receivable report (`account_reports`), which buckets open invoices by due date.
- Business reason: req. 6, customer side.
- Pitfalls: "since when" comes from `account.move.invoice_date_due`, so without a payment term an invoice is due on
  its invoice date. Follow-up reminders run from a cron, which is disabled on demo targets.
- Sources: `knowledge/20.0/accounting/payment_terms.md`

## Custom fields created, for your evaluation
| Field | Why standard was not enough | Standard fallback if you drop it |
|---|---|---|
| `res.partner.x_customer_type` | Exclusive, groupable classification; tags are not exclusive | Contact tags (`res.partner.category`) "Direct", "Agency", ... |
| `sale.order.x_billing_method` | Records the agreed invoicing method and its changes (tracked) | Order tags, or a note; invoicing works the same without it |
| `sale.order.line.x_start_date` | No date on the order line in 20.0; needed per medium/venue | Period written in the line description (flows to invoice, not filterable) |
| `sale.order.line.x_end_date` | Same as above | Same as above |

Two view extensions only show these fields and the standard balances (`amount_invoiced`, `amount_unpaid`): `res.partner.form.vantage.customer_type` and
`sale.order.form.vantage.campaign`. The list extension `sale.order.list.vantage.balance` only shows standard
fields. The opportunity brief uses team properties, which are standard and not custom fields.

## Not covered by this plan
- **Line-level quotation history (req. 4, partial).** Standard tracking logs, with author and timestamp:
  - customer, salesperson, state, `amount_untaxed` and `amount_total` changes;
  - every PDF sent, attached in the chatter as a snapshot.
  It does not log which line, discount, date or venue changed, because `sale.order.line` is not a tracked document.
  Line-level history needs development (an `_inherit` of `sale.order.line.write` posting to the order's chatter).
- **Reminder to invoice the second 50% before the start date.** It needs an automation rule (`base_automation`) or
  a scheduled activity; it was left out to keep the plan configuration-only.
- **Mexican CFDI for down payments** (relation type 07, "anticipo"): see the l10n_mx area.
- **Dates on the quotation/invoice PDF.** Showing `x_start_date`/`x_end_date` on the PDF needs a report template
  extension (QWeb) or Studio (`web_studio`, not installed); neither is reachable as configuration through `ofa`.

## Glossary
- **Campaign**: one sale; in Odoo, one `sale.order` whose number is the campaign code.
- **Campaign line**: medium × venue × period; one `sale.order.line`.
- **Down payment**: an advance invoice from the order (`sale.advance.payment.inv`), deducted from the final
  invoice.
- **Amount Remaining (pending)**: `sale.order.amount_unpaid`, the part of the order total not yet invoiced,
  down payments included.
- **Lead properties**: per-team fields on opportunities defined without code (`crm.team.lead_properties_definition`).
