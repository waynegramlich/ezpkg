# 6.21 Test the README copy of the bootstrap

`README.md` now shows the bootstrap twice: once inside the Quick Start
program, and again on its own in "Enabling `AltVEnv` for Your Program",
where readers copy it from.  The test suite checks only the first copy
(`test_the_quick_start_is_current` compares it with `quick_start.py`).

When the bootstrap next changes (a `nopip5`, say), `quick_start.py` and
the Quick Start copy will be updated, because that test fails until
they are, but nothing will complain about the copy in "Enabling".
Readers would then paste an old bootstrap into their programs.

Add a test that finds the bootstrap in "Enabling" and fails unless it
is the same as the one in `quick_start.py` (the same Part 2 imports and
the same Part 3 code, by `bootstrap_fingerprint`).
