# 7.5 Keep dependencies and imports in sync

Having to add every package to Part 1's `dependencies` by hand is a
friction point (Wayne, 2026-10-15), and so is a package left there
after its import was deliberately removed.  `EZPkg` should detect any
discrepancy between a program's imports and its `dependencies`, and
offer to fix it.  Deliberately
held back until `T.uttat` was done, to rehearse a fix that has to ship
before the pypi.org release (`T.utpat`).

## What Exists

`scan_imports` already finds, on every ordinary run, imports Part 1
does not cover, and warns once per change (`T.siofr`).
`import_problems` names the providing distribution from installed
metadata.  `EZPkg.ask` and `with_script_toml` already edit Part 1
after asking, keeping encoding and line endings (`T.srdisb`).

## The Design (agreed with Wayne, 2026-10-15)

1. **The target.**  The `dependencies` list the imports imply: each
   imported module's package, in the order of each module's first
   appearance in the file.  When `dependencies` equals the target,
   nothing is said.  A missing package, an unused one and a wrong order
   are all just "not the target".
2. **Imports.**  Only the top-level name counts (`from yaml.loader
   import Loader` is `yaml`), anywhere in the file.  Never counted:
   relative imports, `from __future__`, the standard library, `ezpkg`,
   modules beside the program.  An import inside `try: ... except
   ImportError` is optional: it never demands a dependency, but if its
   package is declared it counts as used and sets its position.  An
   import whose package came along with another (covered by the
   approvals) never demands one either.
3. **Packages no import explains** keep their place after the same
   neighbour: one kept with `k` (recorded in the program as `[tool.ezpkg]
   unimported = [...]`), and one whose modules are unknown here (e.g.
   `pywin32; sys_platform == 'win32'` on Linux).
4. **Names.**  An addition's package comes from this Python's metadata
   if it has it, else `MODULE_PACKAGES`, else the module's own name, and
   is downloaded and checked to contain its module before anything is
   written.
5. **Asking.**  On any discrepancy, once per change of the imports or
   `dependencies` (first run included):

   ```
   EZPkg: prog.py: its `dependencies` (lines 5-6) and its imports
   (lines 14-15) disagree.
   See the discrepancy list? [o=>Once/a=>Always/n=>No/d=>Don't ask again]
   ```

   `a` skips this question from then on; `d` never asks about this
   program again; both are confirmed and say how to undo them.  Then,
   in line order, one question per addition (`y`/`n`) and per removal
   (`y`/`n`/`k`): the answer is the intent, since `EZPkg` cannot know
   whether an import is coming or going.  Order is never asked about.
6. **Approving.**  The changes to `dependencies`, one entry per line,
   with the nearest unchanged entry (or `[`/`]`) above and below each
   change as an anchor, then `Make these changes? [y=>Yes/n=>No]`.
   Additions are fetched and checked first, then the file is edited
   once (encoding and line endings kept), and one line reports each
   change.
7. **`EZPkg` only edits `dependencies`** (and `[tool.ezpkg]`).  It never
   adds, removes or reorders an import; the one exception is the
   author's own `# type: ignore` comment copied onto an import whose
   package was added, if the other declared imports carry one.
8. **No terminal**, or `n`/`d`: the discrepancy is warned about once per
   change and nothing is edited.
9. **With an approvals file**, an addition is refused by the approvals
   check like any new package; the message points to
   `EZPKG_APPROVE=write`.
11. **Version ranges (Wayne, 2026-10-15).**  An entry `EZPkg` adds
    gets a range from the version it ran with: always a floor
    (`>=X.Y.Z`), and a conservative cap: `<0.(x+1)` for `0.x`,
    `<(major+1)` for majors 1-9, none from 10 (calendar versions such as
    `pip 25.2` and `certifi 2025.8.3`).  So additions are fetched and
    proved before the changes are shown, and the display shows the real
    range.  Entries the author wrote are never changed during
    development.  At release (`EZPKG_APPROVE=write`), `offer_ranges`
    asks once whether to give each bare entry (a name alone) the range
    of its approved version, so a `.py` sent alone cannot get "the wrong
    packages" (Wayne).
10. **The bootstrap does not change.**  Shipped through test.pypi.org
    (`./release_check.py testpypi`), then `T.utpat`.
