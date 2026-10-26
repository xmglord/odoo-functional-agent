---
title: Online signature, online payment and quotation validity
area: sales_crm
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales/sales_quotations/get_paid_to_validate.html, https://www.odoo.com/documentation/20.0/applications/sales/sales/sales_quotations/get_signature_to_validate.html, odoo/addons/sale/models/res_company.py@20.0, odoo/addons/sale/wizard/res_config_settings.py@20.0, odoo/addons/sale/models/sale_order.py@20.0, odoo/addons/sale/controllers/portal.py@20.0, odoo/addons/sale/models/payment_transaction.py@20.0, odoo/addons/sale_management/models/sale_order_template.py@20.0]
verified_on: 2026-10-26
verified_against: [source, docs]
modules: [sale, payment]
models: [res.company, sale.order, sale.order.template, payment.transaction, res.config.settings]
settings: [portal_confirmation_sign, portal_confirmation_pay, prepayment_percent, quotation_validity_days]
---

## When to use
- If customers should accept quotations themselves from the link in the email, keep **Online Signature**
  (`portal_confirmation_sign`, on by default), because the customer's signature on the portal confirms the order
  without a salesperson.
- If the business wants money before it commits (made-to-order goods, event bookings), enable **Online Payment**
  (`portal_confirmation_pay`) with a **prepayment** percentage (`prepayment_percent`), because the quotation is then
  confirmed only when that share is paid through a payment provider.
- If quotations must expire (prices valid for 15 days), set **Default Quotation Validity**
  (`quotation_validity_days`); 0 disables expiration.
- If only some offers need signature or prepayment, set the flags per quotation template or per order instead of
  company-wide.

## Configuration
- Company fields (module `sale`), exposed as related settings fields of the same name:
  - `res.company.portal_confirmation_sign` ("Online Signature", default true)
  - `res.company.portal_confirmation_pay` ("Online Payment", default false)
  - `res.company.prepayment_percent` ("Prepayment", default 1.0, **fraction 0-1**; constraint "must be a valid
    percentage" while online payment is on)
  - `res.company.quotation_validity_days` ("Default Quotation Validity", default 30, must be >= 0)
- Per order (computed from the company at creation, stored, writable): `sale.order.require_signature`,
  `sale.order.prepayment_percent` (0 when online payment is off), `sale.order.validity_date`. Signature results:
  `signature`, `signed_by`, `signed_on`.
- Per template: `sale.order.template.require_signature`, `prepayment_percent`, `number_of_days` override the
  company values on orders that use the template (see the quotation templates entry).
- Online payment needs at least one enabled payment provider (`payment.provider`, module `payment`). The settings
  action `action_sale_start_payment_onboarding` starts the provider onboarding.
- Confirmation flow: signing on the portal writes `signed_by`, `signed_on`, `signature` and, if no payment is due,
  confirms the order (`_validate_order` → `action_confirm`). A payment transaction confirms the quotation when
  `amount_paid` reaches `prepayment_percent * amount_total`.

## How to verify
- Company: read `portal_confirmation_sign`, `portal_confirmation_pay`, `prepayment_percent`,
  `quotation_validity_days` on `res.company`.
- New quotation: `sale.order.require_signature` and `prepayment_percent` equal the company (or template) values;
  `validity_date` is today plus `quotation_validity_days`.
- After the customer signs: `signed_by` and `signed_on` set, `state == 'sale'` (when no prepayment is due).
- After payment: `amount_paid` >= `prepayment_amount` and `state == 'sale'`; `transaction_ids` lists the
  `payment.transaction`.

## Pitfalls
- `prepayment_percent` is a fraction (0.3 = 30%), unlike the down payment wizard's 0-100 `amount`.
- Changing the company flags does not update existing quotations: `require_signature` and `prepayment_percent` are
  stored on each order when it is created. Templates also keep the values they had when created.
- Turning online payment on with `prepayment_percent = 0` is reverted by the settings onchange (it turns
  `portal_confirmation_pay` off).
- The portal flows (signature canvas, payment form) cannot be exercised over JSON-2; on a demo database, verify the
  configuration fields and, for the effect, write `signed_by`/`signed_on` and call `action_confirm` only as a
  simulation, labelled as such.
- An expired quotation (`is_expired`) cannot be signed or paid online.
- Automatic invoicing after payment is a separate company flag, `sale_automatic_invoice` (see the invoicing policy
  entry).

## Alternatives
- Manual confirmation by the salesperson after an emailed PDF is signed, with signature off.
- Down payments after confirmation when the business accepts the order first and collects an advance later.
- Payment terms with an immediate installment when the invoice, not the quotation, should carry the upfront part.
