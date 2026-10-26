---
title: Discounts on sales order lines
area: good
odoo_version: 20.0
edition: community
source: [https://www.odoo.com/documentation/20.0/applications/sales/sales.html, odoo/addons/sale/wizard/res_config_settings.py@20.0]
verified_on: 2026-10-23
verified_against: [source]
modules: [sale]
models: [sale.order.line]
settings: [group_discount_per_so_line]
---

## When to use
If the business gives per-line discounts, enable the discount setting because the field is hidden otherwise.

## Configuration
Setting `group_discount_per_so_line` on `res.config.settings`.

## How to verify
Read back `discount` on `sale.order.line`.

## Pitfalls
None for this fixture.

## Alternatives
Pricelists.

## Mexico notes
Nothing specific.
