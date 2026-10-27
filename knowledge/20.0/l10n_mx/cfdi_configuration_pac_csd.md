---
title: CFDI configuration and stamping (PAC, CSD certificate, test environment)
area: l10n_mx
odoo_version: 20.0
edition: enterprise
source: [enterprise/l10n_mx_edi/__manifest__.py@20.0, enterprise/l10n_mx_edi/models/res_company.py@20.0, enterprise/l10n_mx_edi/models/res_config_settings.py@20.0, enterprise/l10n_mx_edi/models/certificate_certificate.py@20.0, enterprise/l10n_mx_edi/models/l10n_mx_edi_document.py@20.0, enterprise/l10n_mx_edi/models/account_move_send.py@20.0, enterprise/l10n_mx_edi/models/account_move.py@20.0, enterprise/l10n_mx_edi/demo/demo_cfdi.xml@20.0, enterprise/l10n_mx_edi/data/neutralize.sql@20.0, enterprise/l10n_mx_edi/data/ir_cron.xml@20.0, odoo/addons/certificate/models/certificate.py@20.0, odoo/addons/account/models/account_move.py@20.0]
verified_on: 2026-10-27
verified_against: [source, live]
modules: [l10n_mx_edi, certificate]
models: [res.company, res.config.settings, certificate.certificate, certificate.key, account.move, account.move.send.wizard, l10n_mx_edi.document]
settings: [l10n_mx_edi_pac, l10n_mx_edi_pac_test_env, l10n_mx_edi_pac_username, l10n_mx_edi_pac_password, l10n_mx_edi_certificate_ids, l10n_mx_edi_fiscal_regime]
---

## When to use
- A Mexican invoice only has fiscal value once a PAC (an SAT-authorized certification provider) stamps it. To stamp,
  the company needs: the Enterprise module `l10n_mx_edi`, a PAC account, and its CSD (the SAT certificate and
  private key the company signs with). Configure them before going live; until then use the PAC test environment.
- For demos and tests, keep `l10n_mx_edi_pac_test_env = True`: Odoo then uses test credentials shipped in the
  module for Quadrum (`finkok`) and Solucion Factible (`solfact`), and the stamps have no fiscal effect.
- A company created from scratch cannot stamp even in test mode without a CSD whose RFC matches its own. In a demo
  database, stamp with the demo companies 4 (`base.demo_company_mx`, Quadrum) or 5 (`base.demo_company_2_mx`,
  Solucion Factible) as they ship.

## Configuration
- Module: `l10n_mx_edi` (Enterprise), auto-installed with `l10n_mx`; depends on `account_accountant`, `l10n_mx`,
  `product_unspsc`, `certificate` (`__manifest__.py@20.0`).
- Company / settings fields (`res_company.py`, `res_config_settings.py`, settings are related to the company):
  - `l10n_mx_edi_pac`: `finkok` ("Quadrum", default), `solfact` ("Solucion Factible"), `sw` ("SW
    sapien-SmarterWEB");
  - `l10n_mx_edi_pac_test_env` (Boolean);
  - `l10n_mx_edi_pac_username`, `l10n_mx_edi_pac_password` (`groups='base.group_system'`): production credentials;
  - `l10n_mx_edi_certificate_ids`: one2many to `certificate.certificate` (`company_id`);
  - `l10n_mx_edi_fiscal_regime`.
- CSD: a `certificate.certificate` (generic `certificate` module: `name`, `content`, `pkcs12_password`,
  `private_key_id` → `certificate.key`, `date_start`, `date_end`, `is_valid`, `serial_number`, `company_id`) with
  **`scope = 'cfdi_csd'`**. `l10n_mx_edi` adds the scopes `cfdi_csd` and `e_firma` (`certificate_certificate.py`);
  only a valid `cfdi_csd` certificate of the company (or of its root company) is used to sign
  (`_add_certificate_cfdi_values`).
- Stamping from the UI or RPC: `account.move.action_send_and_print` opens `account.move.send.wizard` (context
  `active_model`, `active_ids`); its `action_send_and_print` stamps when the extra EDI `mx_cfdi` ("CFDI") is checked.
  It is checked by default when the invoice needs a CFDI, is not stamped yet and has no PDF
  (`_is_mx_edi_applicable`, `account_move_send.py@20.0`).
- Results: `account.move.l10n_mx_edi_cfdi_state` (`sent` "Signed", `cancel_requested`, `cancel`, `received`,
  `global_sent`, `global_cancel`), `l10n_mx_edi_cfdi_uuid` (fiscal folio), `l10n_mx_edi_cfdi_attachment_id` (the
  XML), `l10n_mx_edi_cfdi_sat_state`; one `l10n_mx_edi.document` row per CFDI with `state` (`invoice_sent`,
  `invoice_sent_failed`, `payment_sent`, ...), `message`, `attachment_uuid`, `sat_state`, `invoice_ids`, `move_id`.
- Cancellation: `button_request_cancel` on the invoice, wizard `l10n_mx_edi.invoice.cancel`, reasons `01` ... `04`
  (`CANCELLATION_REASON_SELECTION`).
- SAT status: daily cron `l10n_mx_edi.ir_cron_update_pac_status_invoice`, or the "Update SAT" button
  (`l10n_mx_edi_cfdi_try_sat`).
- Demo data (`demo/demo_cfdi.xml@20.0`): company 4 is `finkok` + test env, company 5 `solfact` + test env, both
  regime `601`, each with one demo CSD. `data/neutralize.sql` forces `l10n_mx_edi_pac_test_env = true` on a
  neutralized database copy.

## How to verify
- Company: `l10n_mx_edi_pac`, `l10n_mx_edi_pac_test_env`, `l10n_mx_edi_fiscal_regime`, and a
  `certificate.certificate` with `company_id` = the company, `scope = 'cfdi_csd'`, `is_valid = True` (live, companies
  4 and 5; the fixture's new company has none).
- After sending: invoice `l10n_mx_edi_cfdi_state = 'sent'` and `l10n_mx_edi_cfdi_uuid` set; one
  `l10n_mx_edi.document` with the invoice in `invoice_ids`, `state = 'invoice_sent'`, `attachment_uuid` set and no
  `message`. Scenario `scenarios/20.0/l10n_mx/l10n_mx_invoice_stamp.json` stamps live with Solucion Factible test.
- Do not check `l10n_mx_edi_cfdi_sat_state = 'valid'` on test stamps: the documents stayed `not_defined` live.

## Pitfalls
- **Stamping needs the internet.** Even in test mode Odoo calls the PAC's public test service; a database without
  network access gets a PAC error instead of a stamp (expected from the code path; a run without network was not
  observed for this entry).
- **The demo CSDs expire**: company 5's on 2027-01-18, company 4's on 2027-05-18 (`date_end`, live). After that,
  stamping with that company fails until the template is rebuilt from a newer `l10n_mx_edi`.
- The SW PAC (`sw`) needs a username and password even in test mode; only Quadrum and Solucion Factible work with
  the shipped test credentials.
- With the test environment off and no `l10n_mx_edi_pac_password`, sending fails with "No PAC credentials
  specified."; with no valid `cfdi_csd` certificate, with "No valid certificate found".
- A certificate uploaded with another `scope` (for example `general`, or the `e_firma` FIEL used for SAT downloads)
  is ignored for signing even if valid.
- A PAC rejection raises a `UserError` from the send wizard (HTTP 422 over JSON-2) and keeps the reason on
  `l10n_mx_edi.document.message`; retrying after fixing the invoice moves the same document row to `invoice_sent`.
- A stamped invoice cannot be reset to draft: `button_draft` raises "You can't reset to draft those journal entries.
  You need to request a cancellation instead." (`odoo/addons/account/models/account_move.py@20.0`, through
  `_need_cancel_request`, which `l10n_mx_edi` extends). Request the cancellation first.

## Alternatives
- An external stamping service or another PAC integrated by a third-party module, when the company's PAC is not one
  of the three.
- Configuration-only demos (no stamping) for companies without a CSD: set PAC, test mode and regime and stop before
  sending.

## Mexico notes
Mexico note for customer invoices in the accounting area; listed under "Cross-references" in the l10n_mx index.
