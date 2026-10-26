# LLM Agent Context Log

## 2026-10-26

`refuse_an_edited_bootstrap` always reads `__main__`'s file
(`main_source`), so `pysolidcraft.py`'s `install(bootstrap=
"2026-10-23")`, run on import by `solidcraftcnc_demo.py` (which carries
`2026-10-26`), was refused naming the demo: "It is 2026-10-26, but
calls itself '2026-10-23'".  Also, a module's bootstrap runs the whole
declared install for the main program a second time.

Wayne agreed (2026-10-26): a bootstrap called from a module other than
`__main__` is checked against that module's own file and name, then
returns when the program's install has already run in this process;
if the main program has none, the module's bootstrap acts for the
program as now.

Fixed: `install` notes the calling module (`calling_module`, from the
caller's frame globals; `None` for `__main__`) as `carrier`, and
`refuse_an_edited_bootstrap` reads that file (`source_of`).  `DECLARED`
holds the caches whose program's install ran in this process; a later
bootstrap only checks itself.  Test:
`test_a_modules_bootstrap_answers_for_itself` (passes, edited module
named as `mod.py`, module acting alone).  Seen on the real demo with a
scratch home holding this tree's wheel: `solidcraftcnc_demo.py`
(`2026-10-26`) importing `pysolidcraft.py` (`2026-10-23`, untouched)
ran headless and printed its G-code.
