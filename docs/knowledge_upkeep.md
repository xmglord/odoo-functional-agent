# Knowledge upkeep

The compendium in [knowledge/](../knowledge/README.md) is only as good as its last check against Odoo. Every entry
records what it describes (`odoo_version`, `edition`), where each claim comes from (`source`: source paths with the
branch, or documentation URLs) and when it was last checked (`verified_on`, `verified_against`). The entry rules and
the list of known 20.0 drifts are in [knowledge/README.md](../knowledge/README.md).

## The routine: `ofa stale`

```
ofa stale --lint                 # front matter and required sections of every entry
ofa stale                        # entries verified before the last commit of your Odoo checkout
ofa stale --since 2026-10-01     # entries verified before a given date
ofa stale --area l10n_mx         # one area only
```

Without `--since`, the cut-off date is the committer date of `HEAD` in the Odoo checkout named in the `ofa` config,
so pulling a newer 20.0 lists every entry checked before that code. For each listed entry:

1. Re-read the source paths it cites in the current checkout, and check the names it uses with
   `ofa inspect --target <demo> <model> --fields ...` on a fresh demo database.
2. Fix what changed. A difference from what older guides or the 19.0 code say goes into the known drifts list,
   with the source path and whether 19.0 already behaved that way.
3. Set `verified_on` to the day of the check and `verified_against` to what was checked (`source`, `live`).
4. Run `ofa stale --lint` and the test suite before committing.

Library scenarios in `scenarios/<version>/<area>/` are part of the same check: run them on a fresh demo database
after the template is rebuilt.

Each area's `INDEX.md` keeps an upkeep log: per entry, the agent's tokens and minutes to write or re-check it and
the minutes the author spent reviewing it. It is there to measure what the compendium costs to keep current.

## A new Odoo version

1. Copy the tree: `knowledge/20.0` to `knowledge/21.0` (and `scenarios/20.0` to `scenarios/21.0`). Set
   `odoo_version` in every copied entry.
2. Set the new version in the `ofa` config, point it at the new checkout, and rebuild the template
   (`ofa template build`).
3. Every copied entry is now unverified: re-check each one as above, with `ofa stale --version 21.0`, and start a
   new known-drifts section for the new version.
4. Keep the old tree as it was: plans and examples cite it by path.
