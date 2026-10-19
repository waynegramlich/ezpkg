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

## Agreed, NOT built (next batch)

* S2.4d: platform tag beside `id:`; check the checksum only for a
  wheel of that platform.
* S5.1b: drop `ranges`; a release in `update` mode gives bare entries
  ranges; an author locks an entry by writing a range or `==`.
* S1.5f: a developer's failed first download: one line with `pip`'s
  `ERROR:` reason at `low`/`medium`, full output at `high`.
* S1.5e/S1.5h: the template explains itself, so a developer never
  needs README to start (draft in chat: auto-dependencies, verbosity,
  release, exports, bootstrap, how to upgrade).
* S3.1e: remove a mark once an import explains the entry, only if it
  is exactly one `ezpkg` writes.
* S2.4e: `quick_start.py` ships without approvals.

## Open (given to Wayne, not answered)

1. S5.1c: a release from a dev or source `ezpkg` would range the
   Quick Start's entry `ezpkg>=0.0.1,<0.1`, shutting out `.devN`
   rehearsals; proposed: leave the entry alone then.
2. S1.5h: the template draft; `bootstrap` governing only the bootstrap.
3. S2.2a: wording when nothing new was downloaded.
4. S1.4a: new `ux/drive.py` steps (end user 1.1-1.6, developer
   2.1-2.9, `remove.py` 3.1).
5. Next batch order.
6. `I.ffspo`: the end user's five failure cases, one plain line each.

Lower: S2.2b, S2.4g, S2.4h, S3.3c, S3.3d, S5.1d (see `History.md`'s
batch entry).  README (H.1) waits for the UX work.  Issue numbering:
`S<slice>.<n>`, letter sub-items, never renumbered.

## Next (Wayne)

A GitHub Actions / test.pypi.org run early for OS issues; `ux/drive.py`
redone (much simpler now); README only after the UX work.
