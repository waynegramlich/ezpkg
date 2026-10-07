# 13 How should required packages be declared?

(CLOSED 2026-10-01)  Every case has `PACKAGE = "coverage"` written into it.
Reusing the PEP 723 `# /// script` block instead would make the same program
work under `uv run` for free, and would let one bootstrap serve a list of
packages rather than one.

Various thoughts:
* Wayne (2026-09-22): Sounds like it is worth doing.  The question is when?
* Claude (2026-10-01): Closed with Wayne's agreement.  Step 6.7 settled
  it: a PEP 723 block, read by `install()` with no arguments, and the
  bootstrap fetches only `alt_venv`.
