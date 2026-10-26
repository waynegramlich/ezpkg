# LLM Agent Context Log

## 2026-10-25

`R.pcr` keeps comment lines to 72 columns, and the bootstrap
`2026-10-25` had four over (Part 1's two lines, "Already importable?",
and "Do not edit try block!" on the `raise`).  Wayne: fix it even with
a new bootstrap, since nobody else uses `ezpkg` yet.

Done, not yet released:
* The new bootstrap is `2026-10-26` (the UTC date it will be
  published).  Every comment line is 68 columns or fewer, so
  `bootstrap.py`'s copy, indented 4 more, still fits in 72.  Changes:
  "Fetch u; curl if no certificates.", "python.org Macs.",
  "Present?", and "Do not edit try block!" moved up to the `except`
  line.  Part 1's comment is rewrapped to three lines.
* Fingerprint `177563c5...62ea` added to `BOOTSTRAPS`; `2026-10-25`'s
  text kept in `OLD_BOOTSTRAP_TEXTS`.  Copies changed: `quick_start.py`,
  `README.md`, `QUICK_START`, `bootstrap.py` (`bootstrap_2026_10_26`).
  `SETTINGS_TEMPLATE` and README name `2026-10-26`; `SHIPPING` and the
  refusal tests too.  `__version__` is `0.0.4`.
* Unrelated, seen on the way: local `mypy` 2.4.0 finds 6 errors that
  are already at HEAD (`release.yml` pins 1.9.0, which passes).

Next: the suite; then Wayne commits, and the release (`T.ffrp`'s
procedure) makes `2026-10-26` known on pypi.org.  The other 74
over-long comment lines in the rest of `R.pcr` are not part of this.
