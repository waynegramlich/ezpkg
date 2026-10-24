# LLM Agent Context Log

## 2026-10-22: Created

* Wayne keeps `README.md` open for another sweep on 2026-10-23, before
  `T.utpat`; a bad pypi.org release would embarrass him.
* Since his last read: the Quick Start's Part 2 is one `# Begin` /
  `# End` block; "Enabling" is three steps; "`prog.py.toml` Settings"
  is the template verbatim (Claude recopies it whenever
  `SETTINGS_TEMPLATE` changes); the old notes after it are deleted.
* Same working rules as `T.rd`: proposals in HTML comments with line
  ranges, recomputed just before quoting; re-read before editing.

## 2026-10-23: Halfway through Wayne's re-read

* Wayne has re-read the README up to and including "`prog.py.toml`
  Settings"; the rest of the sweep is still to do.
* Quick Start Part 1 now warns that the `# /// script` lines look like
  comments but are the inline metadata the bootstrap needs.  Claude
  keeps `quick_start.py`, `QUICK_START` and the README's copy identical.
* Wayne rewrote the `prog.py.toml` template in the README; it is now
  `SETTINGS_TEMPLATE`.  Settings: `verbosity`, `update-frequency`,
  `purge-unused-after`, `version`, `release` (a list of forms),
  `bootstrap`, `requires-python`, `dependencies`; keys hyphenated.
  `README.md`'s "Releasing" text and Troubleshooting follow it.
* The shipping bootstrap is now named `2026-10-23` (was `nopip8`);
  only dated names are shown to users, and `nopip3`-`nopip7` stay as
  test fixtures (Wayne).  Later bootstraps are named by their date.
* Working style Wayne wants for these sweeps: give README line numbers
  with every issue, fix only spelling and grammar unless asked, and list
  semantic issues in numbered batches for him to decide.
