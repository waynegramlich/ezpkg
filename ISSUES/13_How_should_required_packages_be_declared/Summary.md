# Summary of `I.hsrpbd` How should required packages be declared?

Every case has `PACKAGE = "coverage"` written into it. Reusing the PEP 723 `#
/// script` block instead would make the same program work under `uv run` for
free, and would let one bootstrap serve a list of packages rather than one.

Last thought: Claude (2026-10-01): Closed with Wayne's agreement. Step 6.7
settled it: a PEP 723 block, read by `install()` with no arguments, and the
bootstrap fetches only `alt_venv`.
