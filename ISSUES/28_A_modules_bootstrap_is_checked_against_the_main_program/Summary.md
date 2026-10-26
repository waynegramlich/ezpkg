# Summary of `I.mbicamp` A modules bootstrap is checked against the main program
Fixed 2026-10-26 in `ezpkg` 0.0.6 (see `I.cernb` for the runs).
`solidcraftcnc_demo.py` (`2026-10-26`) imports `pysolidcraft.py`
(`2026-10-23`), and `refuse_an_edited_bootstrap` read only `__main__`'s
file, so the module's call was refused naming the demo; a module's
bootstrap also redid the whole install.  Now `install` notes the
calling module (`calling_module`, `carrier`), checks its own file
(`source_of`), and once the program's install has run in the process
(`DECLARED`) a later bootstrap only checks itself; a module's bootstrap
still acts for a program that has none.  Test
`test_a_modules_bootstrap_answers_for_itself`; the real demo ran
headless.  README "How `EZPkg` Actually Works" has a bullet.  Related:
`I.cernb`, `I.r2birae`.
