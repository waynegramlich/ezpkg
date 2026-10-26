# Summary of `I.r2birae` A real 2026-10-25 bootstrap is refused as edited
Fixed 2026-10-26 in `ezpkg` 0.0.6 (see `I.cernb` for the runs); found
while testing `I.mbicamp`.  `find_bootstrap` cut the `try` block where
its code ended, dropping a comment on the last line, so 0.0.4 and 0.0.5
refused every real `2026-10-25` paste as edited (its stored text kept
the comment).  `find_bootstrap` now takes whole lines, and the stored
`nopip5`-`nopip7` and `2026-10-23` texts got back the last-line
comment they were published with.  0.0.1's, 0.0.3's and 0.0.5's Quick
Starts and SolidCraft's `pysolidcraft.py` all pass.  Test
`test_a_pasted_text_is_found_whole`.  Related: `I.mbicamp`, `T.reb`.
