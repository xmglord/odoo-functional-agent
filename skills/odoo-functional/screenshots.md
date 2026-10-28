# Evidence screenshots (best-effort)

Screenshots illustrate a run; they never decide pass or fail. That comes from the read-back assertions in
`test.json`. If any step below fails, stop taking screenshots, leave the remaining evidence as `records.json`,
and say so in the report. Do not retry endlessly or work around a tool.

You need:
- a run directory `plans/<slug>/runs/<run_id>/` that holds `screenshot_targets.json` (written by `ofa test`)
- the target's database name (from `ofa targets`)
- the Firefox DevTools MCP tools (`mcp__firefox-devtools__*`)

Every step uses only the loopback demo server. Never open any other host.

## 1. Check the browser

1. Run `ss -tln | grep -E ':(2828|9222)\b'`. If nothing listens, ask the user to start the MCP browser profile.
   Do not launch it yourself, and do not launch it again when it is already up: that opens extra windows.
2. Tell the user to keep the browser window **visible on screen** (not covered, minimized or on another
   workspace) until you say you are done. With the window off screen, pages may stop painting.
3. Call `list_pages` and reuse the open tab; use `new_page` only if there is none.
4. Do not rely on `set_viewport_size`: on this setup it does not change the size. Firefox needs
   `-remote-allow-system-access` for it, which the MCP profile is not started with; firefox-devtools-mcp 0.10.7
   answers "System access is required", and an earlier version answered success without resizing (every screenshot
   of the examples is 1228 x 662). After logging in, read `[window.innerWidth, window.innerHeight]` with
   `evaluate_script`: at 1024 px wide or more Odoo shows its desktop layout. Narrower than that, ask the user to
   widen the window. Say the actual size in your reply.

## 2. Log in to the demo database

The demo data of a provisioned database has the user `admin` with password `admin`. These credentials exist only
in demo databases served on loopback.

1. `navigate_page` to `http://127.0.0.1:8070/web/login?db=<db>`. Then read `document.URL` with `evaluate_script`.
   If it ends in `/web/database/selector` ("The database manager has been disabled"), the browser still holds a
   session for a database that no longer exists, from an earlier run. That first request has already reset the
   session: `navigate_page` to the same login URL **once** more. If it lands on the selector again, stop and say
   so.
2. `take_snapshot` with `selector: "form"`. Fill the email input with `admin` and the password input with
   `admin` using `fill_by_uid`.
3. Check that both fields actually hold the values before submitting:
   `evaluate_script` with
   `() => [document.querySelector('input[name=login]').value, document.querySelector('input[name=password]').value.length]`
   must return `["admin", 5]`.
4. `click_by_uid` on "Log in", then wait until the browser has left the login page before navigating anywhere:
   `evaluate_script` with `timeout: 25000` and
   `() => new Promise(r => { const t0 = Date.now(); const tick = () => { const ok = new URL(document.URL).pathname.startsWith('/odoo'); if (ok || Date.now() - t0 > 20000) { r({ok, url: document.URL}); } else { setTimeout(tick, 250); } }; tick(); })`.
   Navigating while the log-in is still being submitted cancels it, and the next page lands on the database
   selector.

## 3. One screenshot per target

For each entry `{scenario, label, model, id, url}` in `screenshot_targets.json`:

1. `navigate_page` to its `url` (`http://127.0.0.1:8070/odoo/<model>/<id>`). A `BiDi command timeout` error here
   is **not** a failure: Odoo often finishes loading after the browser command gives up.
2. Wait until the page really shows that record. Use `evaluate_script` with `timeout: 35000`, with the path
   filled in:

   ```js
   () => new Promise(r => { const t0 = Date.now(); const tick = () => { const ok = new URL(document.URL).pathname === '/odoo/<model>/<id>' && !!document.querySelector('.o_form_view'); if (ok || Date.now() - t0 > 30000) { requestAnimationFrame(() => r({ok, title: document.title, waited_ms: Date.now() - t0})); } else { setTimeout(tick, 250); } }; tick(); })
   ```

   - `ok: true`: continue.
   - The title is `500 Internal Server Error`: navigate to the same URL once more and wait again. The first web
     client load for a user can fail once while Odoo sets up its chat bot.
   - Anything else after that: **do not take the screenshot**, because it would show the wrong page. Mark this
     target as not taken.
   - Scripts passed to `evaluate_script` must not mention navigation or network APIs (`location`, `href`,
     `fetch`, ...). The plugin's guard blocks them, which is why the wait reads `document.URL`.
3. Check that the page is painting:
   `() => new Promise(r => { let f = false; requestAnimationFrame(() => f = true); setTimeout(() => r(f), 1000); })`
   must return `true`. If it returns `false`, ask the user to bring the window on screen, then check again once.
4. `screenshot_page` with `saveTo` set to the **absolute** path of `~/.firefox-devtools-mcp/output/<name>` (expand
   `~` yourself, for example from `echo ~`), where `<name>` is
   `<scenario>_<label>.png` with the label in snake_case (lowercase; every run of characters other than `a-z0-9`
   becomes `_`). The MCP server only writes absolute paths inside that output directory; it refuses the run
   directory. Do not ask for the server to be restarted with unrestricted save paths.
5. Move the file into the run: `mv ~/.firefox-devtools-mcp/output/<name> plans/<slug>/runs/<run_id>/screenshots/<name>`
   (create `screenshots/` first).
6. Open the PNG with the Read tool and confirm it shows the expected record (the record name in the breadcrumb,
   the expected status). If it does not, delete it and mark the target as not taken.

## 4. Link them from the report

In `plans/<slug>/runs/<run_id>/report.md`, section `## Evidence`, each target's line ends with
`screenshot not taken`. For every screenshot you kept, replace that text with
`[screenshot](screenshots/<name>)`. Leave the others as they are, and list in your reply which targets have no
screenshot and why.

## 5. Log out

When the screenshots are done (or the procedure stopped after logging in), log out, so that the browser does not
keep a session for this database: once it is dropped, that session sends the next run's login to the database
selector.

1. Log out with clicks, not with a script: the plugin's guard refuses `.click()` inside `evaluate_script`.
   `take_snapshot` with `maxLines: 40` and no selector (a selector on the menu bar has failed with "str.substring
   is not a function"). In the top bar, the user menu is the last `button` of the systray, the one holding the
   avatar `img` and "User is online"; `click_by_uid` on it. Then `take_snapshot` with
   `selector: ".o-dropdown--menu"` and `includeAll: true`, and `click_by_uid` on the `menuitem` whose text is
   "Log out". (`/web/session/logout` answers 405 to a plain navigation: logging out is a POST.)
2. Check that `document.URL` now contains `/web/login`. Say in your reply whether the log-out worked.
