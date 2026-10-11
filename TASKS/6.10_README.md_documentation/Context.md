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
  imports its own copy.  Fixed 2026-10-10: `nopip4` uses an importable
  `alt_venv`, and `provide()` skips what `satisfied()` says is already
  installed.  Better still, `ALT_VENV_EXPORT=uv` writes a stripped,
  pinned `prog-uv.py` with its locks (`T.ewar`), so the README can say
  "start with `AltVEnv`, export for `uv`".
* **The PyPI names are free**, checked 2026-10-02: `alt_venv`,
  `alt-venv` and `altvenv` all return 404.  The bootstrap installs
  whatever PyPI serves under `alt_venv`, so anyone who registers it
  first owns every program that pastes it.  Worth claiming soon.
* The facts the README rests on:
  * The shipping bootstrap is `nopip4` (since 2026-10-10; `nopip3`
    before): **35 pasted lines** -- its 32 line body plus
    `import importlib`, `import pathlib` and `import sys`.  It first
    uses an `alt_venv` that is already importable.  Since 2026-10-02
    it calls `AltVEnv().install(bootstrap=...)` itself, so a program's
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

Later on 2026-10-10, after `ALT_VENV_EXPORT=uv` shipped, Wayne reopened the
README for a section-by-section pass:
* **Done:** the introduction (problem, solution, life-cycle: paste the
  35-line bootstrap, fetch on demand, then email the `.py` or export as
  `zipapp` or `uv`), the Quick Start, and the Download Prompt (now one
  paragraph).  `~/.alt_venv/` is introduced at first use.  The "Your Own
  Program" stub moved into the intro of "Anatomy of an `AltVEnv`
  Program", which now sits after Alternatives with `###` Parts.
* `QUICK_START`, `quick_start.py` and the README use
  `# type: ignore[import-not-found]  # For mypy.`; mypy rejects text
  appended inside a `type: ignore` comment.
* **Next:** Author Package Management, which Wayne has not read.  Its
  HTML freeze note is stale; it should present the `pins`, `zipapp` and
  `uv` exports and say why `zipapp` is pure Python only.  Then the
  Alternatives `zipapp` and "Why not just use `uv`?" bullets (say
  `AltVEnv` exports to both), and Miscellaneous.
* Claiming the PyPI name and making the Quick Start work wait for the
  very end of the project, at Wayne's word.
