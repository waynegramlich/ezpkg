# 6.19 Scan the imports on first run

Run the `T.cibe` import check during ordinary runs too, not only at
export, so the author learns about every missing package at once
instead of one `ModuleNotFoundError` per run, and learns early about a
package their own Python happens to have.  It only warns (an export
still refuses), and it is remembered in `~/.alt_venv`, so it runs again
only when the program's imports, `dependencies` or approvals change.
Goes with the README rule that all imports come after the bootstrap.
