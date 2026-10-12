# Summary of `T.cibe` Check the imports before exporting

Every `ALT_VENV_EXPORT` form (`pins`, `zipapp`, `uv`) now checks the
program's imports before writing anything (`AltVEnv.check_imports`,
using `program_imports`, which reads the source with `ast`).  An import
that works only because the author's own Python happens to have the
package, or that finds nothing at all, is listed on standard error with
its line number, and the export fails.  Nothing is checked during
ordinary runs: while developing, an `ImportError` already tells the
author.  Accepted without complaint: the standard library, `alt_venv`,
a module beside the program, and any package that Part 1 declares or
the approvals record (so packages that came along count).  Skipped:
imports in a `try` that catches `ImportError`, under `TYPE_CHECKING`,
relative imports, and platform-guarded imports that find nothing.
Package names come from installed metadata and are never guessed.
Grew out of the README's "is this package preinstalled?" question in
`T.rd`, which has no stable cross-platform answer.
