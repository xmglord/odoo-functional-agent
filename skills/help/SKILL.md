---
name: help
description: Explain how to use the odoo-functional-agent plugin and check whether this machine is ready for it. Read-only. Use when the user asks about the plugin itself: how to use it, what it can do, how to start or whether it is set up ("how do I use this plugin?", "what can this plugin do?", "how do I get started?", "is it ready?", "¿cómo se usa este plugin?", "¿qué puede hacer?", "¿cómo empiezo?", "¿está listo?"). Not for a business requirement or a request to configure or test Odoo, which go to odoo-functional, nor for a question about how Odoo works, which goes to odoo-explain.
---

# Help for the plugin

Reply in the user's language. Keep it short: the flow, how to ask, and whether this machine is ready.

## Rules

- Read-only. Run only the two commands below. Do not start the server, create or change a database, or open a browser.
- Do not run `ofa` here, even for a read-only subcommand: it turns on the session guard, and a person asking for help
  is not using the agent yet. `ofa-check` prints the same information without that.
- If the user brings a requirement or an Odoo question, stop helping and let the skill below take over.

## The flow

Say this in a few lines:

1. The user invokes `odoo-functional` with the requirement in the same message.
2. It checks the setup, starts the local server, creates a demo database and may ask up to 3 questions.
3. It stops with the plan and the Test plan. Nothing is applied until the user approves explicitly.
4. It applies the plan, tests it and reports pass or fail for each need. It never touches a real Odoo.

## How to ask for each thing

Give these examples, translated when the user does not write in English. Advise typing the skill's name.

- Configure and test something: `/odoo-functional-agent:odoo-functional We sell with discounts and need a manager's
  approval above 10%.`
- Use a demo database that already exists: add a line `Target: <name>` to that message.
- Understand Odoo: `/odoo-functional-agent:odoo-explain when should I use lots instead of serial numbers?`
- See this help: `/odoo-functional-agent:help`.

## Check the environment

Run `ofa-check`, then `ss -tln | grep -E ':(2828|9222)\b'`, as two separate commands. Report what is ready and, for
what is not, what is missing and how to fix it. Setup steps are in `${CLAUDE_PLUGIN_ROOT}/docs/setup.md`.

| What you see | What it means | Fix |
|---|---|---|
| `ofa-check: command not found` | the plugin is not enabled in this session | enable it and start a new session |
| `Python 3.11 or newer is required` | `ofa` needs Python 3.11 or newer | install it |
| `FAIL` on `config readable` | no valid `ofa` config | step 3 of the setup |
| `FAIL` on `odoo conf hardened` | the Odoo config lacks a required setting | step 2 of the setup |
| `FAIL` on `server port answers`, `"alive": false` | the server is stopped | nothing: `odoo-functional` starts it |
| `"alive": true`, `"port_answers": false` | the server is still starting | wait and check again |
| `"alive": false`, `"port_answers": true` | something else is using the server's port | free the port |
| nothing listed under `ofa targets` | no demo database yet | nothing: `odoo-functional` creates one |

`ofa-check` cannot see whether the template database exists. If this is the first use, tell the user that step 4 of
the setup must be done once, and that `odoo-functional` will fail creating a demo database without it.

Firefox is optional and only for screenshots. If either port is listening, say it is available. If not, say the run
still works and the evidence will be the records the tests read back; the user can start the browser when asked.
