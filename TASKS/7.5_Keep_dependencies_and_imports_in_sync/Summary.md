# Summary of `T.kdaiis` Keep dependencies and imports in sync

Done 2026-10-19.  A developer's `dependencies` (a `prog.py` with a
`prog.py.toml`) follow the imports silently: `reconcile` adds an
entry for a new import (named from metadata, `MODULE_PACKAGES` or the
module, proved by `EZPkg.prove`, ranged by `version_range`), removes
one whose import went, keeps the import order, copies the author's
`# type: ignore`, and restarts the program after the edit.  An entry
no import explains is kept and marked (`needed_by`), and the mark goes
once an import explains it (`MARK`).  The question-based design in
`Details.md` items 5, 6, 8 and 9 was replaced by `T.abfd`'s redesign;
an end user's program is never edited.  A release ranges bare entries.
Seen end to end in `ux/drive.py` steps 2.2-2.7.  Related: `T.abfd`,
`T.eui`.
