---
title: Purchase order approval levels and order locking
area: purchase_inventory
odoo_version: 20.0
edition: community
source: [odoo/addons/purchase/models/res_config_settings.py@20.0, odoo/addons/purchase/models/res_company.py@20.0, odoo/addons/purchase/models/purchase_order.py@20.0, odoo/addons/purchase/security/purchase_security.xml@20.0]
verified_on: 2026-10-26
verified_against: [source, live]
modules: [purchase]
models: [res.company, res.config.settings, purchase.order]
settings: [po_order_approval, po_double_validation, po_double_validation_amount, lock_confirmed_po, po_lock]
---

## When to use
- If purchases above an amount must be signed off by a manager before they go to the vendor, enable **Purchase
  Order Approval** (`po_order_approval`) with a **Minimum Amount** (`po_double_validation_amount`), because orders
  at or above that amount stop in state `to approve` instead of becoming purchase orders.
- If every order, whatever its amount, needs a manager, there is no "always" option: set the minimum amount to `0`.
  The check is `amount_total < threshold`, so with `0` no order passes on amount alone.
- If confirmed orders must not be edited afterwards (prices, quantities agreed with the vendor), enable **Lock
  Confirmed Orders** (`lock_confirmed_po`), because confirmation then sets `locked` on the order.
- If approval rules differ by department or by product category, this setting is not enough: it is one threshold
  per company. See Alternatives.

## Configuration
- Settings (model `res.config.settings`, defined in `odoo/addons/purchase/models/res_config_settings.py@20.0`;
  purchase keeps its settings model in `models/`, unlike sale):
  - `po_order_approval` (boolean, "Purchase Order Approval"). Its `set_values` writes the company field
    `po_double_validation` = `two_step` when true, `one_step` when false.
  - `po_double_validation` (related `res.company.po_double_validation`, selection `one_step` / `two_step`).
  - `po_double_validation_amount` (related `res.company.po_double_validation_amount`, monetary in the company
    currency, default `5000`).
  - `lock_confirmed_po` (boolean, "Lock Confirmed Orders"); `set_values` writes `res.company.po_lock` =
    `lock` / `edit`.
- Plan the booleans (`po_order_approval`, `lock_confirmed_po`) plus the amount; they are what the settings screen
  writes. The company fields follow from them.
- Order flow on `purchase.order` (`state`: `draft` "RFQ", `sent` "RFQ Sent", `to approve`, `purchase`, `cancel`):
  - `button_confirm` moves a `draft`/`sent` order to `purchase` when `_approval_allowed()` holds, else to
    `to approve`.
  - `_approval_allowed()` holds when the company is `one_step`, or when `amount_total` is below the threshold
    converted to the order currency, or when the current user has `purchase.group_purchase_manager`.
  - `button_approve` (the manager's "Approve Order" button) sets `state = 'purchase'` and `date_approve`, and sets
    `locked = True` when the company's `po_lock` is `lock`.
  - `button_unlock` / `button_lock` toggle `locked`.

## How to verify
- Company: `res.company.po_double_validation == 'two_step'` and `po_double_validation_amount` holds the agreed
  amount; `res.company.po_lock == 'lock'` when locking was requested.
- Behaviour, as a user **without** `purchase.group_purchase_manager`: an order with `amount_total` at or above the
  threshold reads `state == 'to approve'` after `button_confirm`; one below it reads `state == 'purchase'`.
- After approval with locking on: `purchase.order.locked == True` and `date_approve` is set.

## Pitfalls
- **Managers bypass the threshold.** A user with `purchase.group_purchase_manager` confirms straight to `purchase`.
  The `ofa_bot` user copies the admin's groups, so it is a purchase manager (observed on a 20.0 demo DB): a
  scenario run as the bot cannot show the `to approve` state. Prove the setting by reading the company fields, or
  confirm as a user who only has `purchase.group_purchase_user`.
- The threshold is compared with `amount_total` (taxes included), converted from the company currency to the order
  currency at `date_order`.
- `button_approve` silently skips orders the current user may not approve (it filters on `_approval_allowed()`);
  it does not raise. Read `state` back after calling it.
- Turning approval off does not release orders already in `to approve`; they still need `button_approve`.
- A locked order (`locked`) cannot be cancelled: `button_cancel` raises until it is unlocked.

## Alternatives
- Purchase Agreements (`module_purchase_requisition`, model `purchase.requisition` with `requisition_type`
  `blanket_order` / `purchase_template`) when the control is a negotiated framework with the vendor rather than an
  internal sign-off.
- Studio approval rules (Enterprise) for per-button, per-group or conditional approvals beyond one company-wide
  amount.
