# LLM Agent Context Log

Earlier entries (the `ux01`-`ux27` review and the designs the
2026-10-19 redesign replaced) are in `History.md`.

## 2026-10-19: State after the redesign (condensed)

`Details.md` "The Design" is the design.  Built, and rehearsed as
`0.0.1.dev202610192143` (`1d21c14`; release run 39329611039,
`release_check` passed, `check.yml` run 39329748088 passed):

* Slice 1, the two modes: `Settings`, `read_settings`
  (`prog.py.toml line N: ...`, "did you mean"), `EZPkg.settings()`
  fills an empty file; `developing()` is "has a `prog.py.toml`".
* Slice 2, the end user: `consent` is `[y=>Yes|n=>No|?=>Explain]:`;
  the `develop/` record holds `agreed: "yes"`; asked once per program,
  ever (S2.1, S2.2), even on a warm run; a no removes the downloads
  (the whole cache on a first run).  `a`, `s`, `FOREVER_APPROVE` gone.
* Slice 3, silent reconciliation: `reconcile` (no questions); the
  record's `imported` tells a removed import from a hand-added entry;
  any comment on an entry keeps it; marks `# pandas needs this for
  excel`, `# pandas needs this`, `# not imported: say why it is
  needed` (S3.4); `import_module("x")` counts as an import; a failed
  fetch or unproved guess retries next run (S3.3a); restart after an
  edit.
* Slice 4, frozen versions: `EZPKG_APPROVE` gone; developer runs
  stamp `exclude-newer` and write approvals; deleting the date line
  upgrades; `too_new` stops a run whose new import is newer than the
  date.
* Slice 5, release: `release = "X.Y.Z"` differing from Part 1's
  `[tool.ezpkg] released` releases once (`release`, `export(form,
  ...)`, `prog-X.Y.Z.pyz` / `prog-X.Y.Z-uv.py`) and exits.
  `EZPKG_EXPORT`, `EZPKG_BOOTSTRAP=check` gone.
* S1.5 `verbosity = none|low|medium|high` (default `low`) replaces
  `report`; `EZPkg.say(level, ...)`.  S1.5g: no `ezpkg:` prefix on
  the developer's sentences; `high` lines keep it.
* S2.4: `prog.ezpkg` gone; approvals are Part 1's `[tool.ezpkg]
  approved = ["name==version  id:<16 hex>", ...]`.  S3.3b: `cull`
  keeps agreed programs' packages.
* S5.1: setting `bootstrap` (`"update"` default, or a published name);
  `update` makes a release replace a stale bootstrap and range the
  `ezpkg` entry; a named one is enforced.  S5.2: never add a bootstrap.
* Tests: `developer_settings`, `run_as_developer`,
  `release_as_developer`; quick suite needs a scratch `HOME` with a
  current `pip.whl` (305 OK, 17 skipped at last count).

## 2026-10-19: Batch built (Wayne: "let's build it")

* S5.1b: `ranges` setting gone; every release gives bare entries
  ranges (`give_ranges`).  `bootstrap` governs only the bootstrap; the
  `ezpkg` entry is ranged at every release (S1.5h, my proposal, not
  objected to).
* S5.1c (Wayne: reasonable): `range_ezpkg` leaves the entry alone
  unless `from_wheel()`.
* S1.5f: a developer's failed fetch is `` `prog.py` did not run: ERROR:
  ... `` plus a hint; all of `pip`'s output at `high`
  (`install_declared`).  End users unchanged (`I.ffspo`).
* S1.5h: `SETTINGS_TEMPLATE` explains itself (what the file means,
  each setting, how to upgrade).  Wayne has not read it yet.
* S3.1e: `MARK` matches exactly `needed_by`'s marks;
  `Discrepancy.unmark`; reconcile says "Unmarked ..." at `medium`.
* S2.4d: `wheel_tag`, `approval_fields`, `approval_tags`; compiled
  wheels get `  tag:<py-abi-plat>` after `id:`; `verify` checks the id
  only for a wheel of that tag (version still pinned).
* S2.4e: already so; guarded by a test.
* Quick suite: 311 run, 1 failure fixed afterwards (the newer-bootstrap
  test now runs a wheel-like copy of `ezpkg`), 17 skipped.

## Wayne's answers, 2026-10-19

* S2.2a: settle the wording in `ux/` (the first-run question when
  every package is already cached).
* S1.4a: the end user's steps come first in `ux/`.
* Later the same day: the paragraph says "they are retained in"
  (Wayne's edit).  A bare Enter asks again silently, uncounted (Wayne).
  `EZPKG_ANSWER_SECONDS` shortens the 5-minute wait, for tests and
  `ux/drive.py` only.  Version 2 of `prog.py` (a `ux` step) needs
  `tabulate` and its cow says so.
* `ux/drive.py` rewritten: end-user steps 1.1-1.12 (first run, later
  runs, a second program, version 2, `remove.py`, `?`, Enter, typo,
  `n`, Control-C, Control-D, no answer).  Old `ux/ux*` files removed
  from the working tree (they are in git).  Developer steps next.
* PowerShell `~` (researched 2026-10-19, for the `remove.py` line):
  Windows PowerShell 5.1 is the inbox shell on Windows 10 and 11 (24H2,
  25H2) and passes `~` to a program such as `py` literally.  PowerShell
  7 (separate install) expands an unquoted `~` for native programs on
  Windows only from 7.6 (GA 2026-03-18, `PSNativeWindowsTildeExpansion`
  mainstream; experimental in 7.5).  `$HOME\.ezpkg\remove.py` works in
  every PowerShell (PowerShell expands `$HOME` itself) but not in
  `cmd.exe`, which needs `%USERPROFILE%`.  Wayne chose: the docs give
  both (`$HOME` for PowerShell, `%USERPROFILE%` for `cmd.exe`); `ezpkg`
  never prints the line, so nothing detects the shell.  README still
  shows the old design and waits for the README pass.
* The list after a yes says "retained", as the question does (Wayne).
* A no on a later program keeps the cache (Wayne agreed to Claude's
  argument: other programs' agreements live there): `newly_filled`;
  the paragraph then says "answer `n` and `second.py` will not run."
* `ux/drive.py` 2.1-2.3 found a double edit (a developer's new import
  edited `prog.py` twice, "changed again after starting it again"):
  `fetching` now asks what `providing` asks, keeping the `ezpkg` pin.
* `I.ffspo` built (see its `Context.md`); Wayne sees the wording next.
* Unread by Wayne, batched for later: `ux/ux01`-`ux15` (all pass).

## Open (given to Wayne, not answered)

1. S1.4a: the end-user step list (given in chat), then developer
   steps; rewrite `ux/drive.py`.
2. `I.ffspo`: the end user's five failure cases, one plain line each.

Lower: S2.2b, S2.4g, S2.4h, S3.3c, S3.3d, S5.1d (see `History.md`'s
batch entry).  README (H.1) waits for the UX work.  Issue numbering:
`S<slice>.<n>`, letter sub-items, never renumbered.

## Next (Wayne)

A GitHub Actions / test.pypi.org run early for OS issues; `ux/drive.py`
redone (much simpler now); README only after the UX work.
