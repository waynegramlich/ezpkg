# Summary of `T.fipab` Flag imports placed above the bootstrap

`imports_above_bootstrap` lists each import that runs before the
bootstrap (not inside a function), except `from __future__` and imports
whose bound names the bootstrap uses, which recognises any bootstrap's
Part 2 without a list to maintain.  `import_problems` reports them, so
an ordinary run warns (`T.siofr`) and an export refuses (`T.cibe`).
README "Enabling" step 3 says so.  Related: `T.siofr`, `T.cibe`.
