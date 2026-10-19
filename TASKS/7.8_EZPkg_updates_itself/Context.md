# LLM Agent Context Log

Earlier entries are in `History.md`.

## 2026-10-19: State (condensed)

* Built and rehearsed (from `0.0.1.dev202610171424`): `meets`
  (orders `.devN` before its release), `own_entry`, `EZPkg.chosen`,
  `EZPkg.switch` (`os.execve` with the chosen tree first on
  `PYTHONPATH`, `EZPKG_SWITCHED`, `EZPKG_PYTHONPATH`; Windows runs a
  child), `EZPkg.switched`.  `install()`: if this `ezpkg` is chosen,
  `T.reb`'s check first; otherwise provide, switch, then the check.
  A bootstrap counts as an import of `ezpkg`, so the entry is wanted
  first.
* The approvals pin `ezpkg` when it came from a wheel (`from_wheel`);
  a source copy is left out.  `for_export` keeps `ezpkg` in an export
  only when the program itself imports it (settles `I.uedepi`).
* Quick Start Part 1: `["ezpkg>=0.0.1.dev0,<0.1", "cowsay"]` (`.dev0`
  admits rehearsals).  At the real release, the Quick Start's and the
  Enabling template's entries become the released version's range.
* `-I`/`-E` ignore `PYTHONPATH`, so a switch then stops with a message.
* Left: Wayne's `zipapp`/`uv` dogfood (now a `ux/drive.py` step), then
  `Summary.md` and close.
