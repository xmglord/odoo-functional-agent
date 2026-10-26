# Smoke: sales discounts, VIP tag and a Mexican subsidiary

This fixture exercises all four operation types on a fresh demo database. It is applied twice by the
live smoke check: the first apply must exit 0, and the second must report every operation as `unchanged`.

## Operations

- [op_010_install_sales] Install `sale_management` (Sales). The demo template already has it, so the
  first apply reports `unchanged` with `pre_state: true`. That result proves nothing about the plan.
- [op_020_line_discounts] Turn on the Discounts setting (`group_discount_per_so_line`), read back
  through `res.config.settings` in the main company's context. If the template already has it on, the
  first apply reports `unchanged` with `pre_state: true`.
- [op_030_vip_tag] Create the contact tag "Smoke VIP" under the key `__ofa__.smoke_vip_tag`. A tag with
  that name made by hand is adopted instead of duplicated.
- [op_040_company_mx] Create the company "Smoke Demo MX SA de CV" with country Mexico and currency MXN.
  Creating a company with a country loads that country's chart of accounts, and `ofa` adds the new
  company to its bot user so later reads on it are allowed.
- [op_050_company_mx_chart] Call `res.company.install_l10n_modules` on the new company, unless it already
  uses the `mx` chart template. Because company creation loads the chart, this is normally `unchanged`:
  the call is a safety net, and `skip_if` keeps re-applies a no-op.
