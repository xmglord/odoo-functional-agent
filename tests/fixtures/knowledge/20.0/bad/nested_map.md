---
title: Entry with a nested map
area: bad
odoo_version: 20.0
edition: community
source: [odoo/addons/sale/models/sale_order.py@20.0]
verified_on: 2026-10-23
verified_against: [source]
settings:
  group_discount_per_so_line: true
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

