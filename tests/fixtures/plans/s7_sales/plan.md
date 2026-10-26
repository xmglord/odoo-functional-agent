# S7: Sales with a Mexican subsidiary (repeatability fixture)

This fixture is the input of spike S7 (requirement R7). It is applied to two fresh demo databases, both
are dumped with `ofa dump` and the dumps must be byte-identical; a second apply on one of them must report
every operation as `unchanged`. It covers all four operation types, a company-scoped setting on a company
the plan creates, records that refer to other `__ofa__` records, and one record adopted through `match`.

## Main company

- [op_010_install_sales] Sales and CRM. The template already has both, so the first apply reports
  `unchanged` with `pre_state: true`; that result proves nothing about the plan.
- [op_015_install_loyalty] Install `sale_loyalty`, which the template does not have, so promotion and
  loyalty programs are ready for later. The first apply reports `created`.
- [op_020_main_sales_settings] Per-line discounts and pricelists. Both are group settings shared by all
  companies; they are saved from the main company's context. If the template already has them on, the
  first apply reports `unchanged` with `pre_state: true`.

## Mexican subsidiary

- [op_030_company_mx] The company "S7 Ventas MX SA de CV", country Mexico, currency MXN. `ofa` adds it to
  its bot user so the later operations can work in it.
- [op_040_company_mx_chart] `install_l10n_modules` on the new company unless it already uses the `mx`
  chart. Creating a Mexican company loads that chart, so this is normally `unchanged`.
- [op_050_mx_quotation_settings] Quotation validity of 15 days and online signature. These settings are
  related to the company, so they are saved in the subsidiary's context and leave the main company alone.
- [op_080_team_mx] The sales team "S7 Ventas MX", owned by the subsidiary.
- [op_090_stage_negotiation] A pipeline stage "S7 Negociacion" that only that team sees.
- [op_110_pricelist_mx] The MXN pricelist "S7 Lista MX" of the subsidiary.
- [op_130_price_install_mx] A fixed price of 1200 MXN for the installation service in that pricelist.

## Shared records

- [op_060_tag_industrial] The contact tag "S7 Industrial".
- [op_070_crm_tag_training] The demo data already has a CRM tag "Training". It is adopted by name under
  `__ofa__.s7_crm_tag_training` and recolored instead of creating a duplicate: the first apply reports
  `adopted`.
- [op_100_customer_mx] The customer "S7 Cliente Industrial SA de CV", a Mexican company tagged Industrial.
  The plan does not set `is_company`: Odoo 20 computes it from the tax id (`vat`) and undoes a written
  value after create, which `ofa apply` reports as `VALUE_NOT_HELD`. The tax id is left to the MX
  localization scenarios.
- [op_120_product_install] The service product "S7 Servicio de instalacion" (code S7-INST), 1500 list price,
  invoiced on order.

## First case

- [op_140_lead_mx] The opportunity with the customer, in the Mexican team, at the negotiation stage, tagged
  Training.
- [op_150_order_mx] The order for that customer in the subsidiary with the Mexican pricelist.
- [op_160_order_line_install] Three installations at 1200 with a 5% discount. The product variant is found
  with `$search` on the template the plan created.
- [op_170_confirm_order] Confirm the order unless it is already a sales order, so a re-apply is a no-op.
