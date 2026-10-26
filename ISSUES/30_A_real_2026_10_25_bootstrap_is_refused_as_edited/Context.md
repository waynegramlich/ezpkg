# LLM Agent Context Log

## 2026-10-26

Found while testing `I.mbicamp` on the real demo.  `find_bootstrap` took
`ast.get_source_segment`, which ends where the code ends, so a comment
on the `try` block's last line was dropped.  The published `2026-10-25`
has `# Do not edit try block!` on its last line, and its stored text in
`OLD_BOOTSTRAP_TEXTS` kept it, so `ezpkg` 0.0.4 and 0.0.5 refused every
real paste of `2026-10-25` as edited (checked with `git show
v0.0.3:quick_start.py`).  The other stored texts (`nopip5`-`nopip7`,
`2026-10-23`) had been captured through the truncating
`find_bootstrap`, though the published ones carry the comment too.

Fixed: `find_bootstrap` takes whole lines, and the four stored texts
get their last-line comment back.  Checked: 0.0.1's, 0.0.3's and
0.0.5's `quick_start.py` and SolidCraft's `pysolidcraft.py` all pass.
Test: `test_a_pasted_text_is_found_whole`.
