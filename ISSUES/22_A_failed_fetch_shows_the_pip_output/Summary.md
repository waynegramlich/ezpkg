# Summary of `I.ffspo` A failed fetch shows the pip output
Fixed 2026-10-19, every case seen end to end 2026-10-22.  An end
user's failed fetch is one plain line, never `pip`'s text, which goes
to `~/.ezpkg/last_failure.txt` for the author (`end_user_failure`):
no network; a pinned version PyPI no longer offers (`unavailable`,
which also reads `pip`'s conflict form, since a locked version that is
gone shows as `ResolutionImpossible`); no wheel for this computer;
anything else as `pip`'s `ERROR:` line, the machine's own noise left
out.  With `ezpkg` already importable, `own_pip` fetches a private
`pip`.  A developer's failed fetch is one line with `pip`'s reason,
naming the `prog.py.toml` line when an entry there caused it.
Related: `T.abfd`, `T.ee`.
