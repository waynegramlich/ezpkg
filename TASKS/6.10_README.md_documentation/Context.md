# LLM Agent Context Log

As of 2026-10-02, `README.md` is nearly finished.  It is Wayne's file;
help when asked, do not edit it unasked, and rewrap his over-long
lines.  Its sections now run: the hook
(problem, answer, happy ending), Quick Start (copy and run
`quick_start.py`, then a read-along of its five `# Part` comments),
Download Prompt, Author Package Management, Miscellaneous,
Alternatives, Conclusion.  What is left:
* **Conclusion.**  Claude proposed, and Wayne was too tired to read:
  (1) replace it with four lines closing the opening story -- list
  packages in Part 1, copy Parts 2 and 3, a single file you can
  e-mail; (2) add short `## Status` and `## License` sections; (3)
  say under Status that Windows never shows the download prompt.
  Also: the repository has no `LICENSE` file, which PyPI and GitHub
  look for.
* **Author Package Management** is a placeholder.  Wayne wants a
  true freeze, to be "functionally equivalent to" `zipapp` (he wrote
  `appap`; Claude read it as `zipapp` and said so).  An HTML comment
  in the section records what a freeze needs: `==` pins in Part 1
  plus the approvals file, perhaps with `ALT_VENV_APPROVE=write`
  printing the pins.  Approvals are keyed by wheel file name, so a
  compiled package approved on one platform is refused on another.
* **Alternatives** is a first pass, unreviewed.  Settled overnight:
  `quick_start.py` does run under `uv run`, but redundantly -- `uv`
  installs `cowsay` into its environment, then the bootstrap fetches
  `alt_venv`, downloads `cowsay` again into `~/.alt_venv`, asks, and
  imports its own copy.  So "works with `uv`" needs that caveat, or a
  code change: `install()` could skip what is already importable.
* **The PyPI names are free**, checked 2026-10-02: `alt_venv`,
  `alt-venv` and `altvenv` all return 404.  The bootstrap installs
  whatever PyPI serves under `alt_venv`, so anyone who registers it
  first owns every program that pastes it.  Worth claiming soon.
* The facts the README rests on:
  * The shipping bootstrap is `nopip3`: **31 pasted lines** -- its 28
    line body plus `import importlib`, `import pathlib` and
    `import sys`.  Since 2026-10-02 it calls
    `AltVEnv().install(bootstrap="nopip3")` itself, so a program's
    author never touches `AltVEnv` or names `alt_venv`.  The label is
    read by nothing, but Wayne wants it; there is no `package=`.
  * What a machine needs: Python 3.11 or later, and a network that
    reaches PyPI on the first run.  No `pip`, no virtual environment,
    no administrator rights.  Verified on Linux only, under 3.11 and
    3.12; Windows and macOS are untried (`I.wmau`, `I.btosc`).
  * The Quick Start cannot work until `alt_venv` is on PyPI.  It was
    verified end to end with `alt_venv` from a local index and `pip`
    and `cowsay` from the real PyPI.
  * `README.md` says the bootstrap's first-run `pip` output is
    visible on purpose, at Wayne's word, and that `AltVEnv` hides
    `pip`'s output unless `pip` fails, which is what the code does.
  * Wayne wants `pip` kept out of the opening sections.

As of 2026-10-10: Wayne chose Claude's Conclusion, which replaced his
(`README.md:332-338`).  Wayne skipped `## Status` and `## License`
(nobody reads them); `LICENSE` now holds the MIT-0 text copied from
`alt_venv.py:37-54`.  Wayne now thinks Author Package Management and
Alternatives (the `uv` double download) are related; they come after the
Conclusion.
