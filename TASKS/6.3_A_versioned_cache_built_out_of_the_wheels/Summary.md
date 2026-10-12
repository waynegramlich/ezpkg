# Summary of `T.vcbow` A versioned cache built out of the wheels

The cache keeps every package version it fetches as its own unpacked
tree under `~/.alt_venv/versions/`, put on `sys.path` per request, with
wheels kept beside their SHA-256 and request records naming the trees.
The last leftover, 6.3.11, was fixed 2026-10-12: a process can import
only one version of a module, so `install` now raises a `RuntimeError`
when a module it is asked for is already imported from another
version's tree, instead of silently returning the first version
(`provide` returns the trees it used; test
`test_a_second_version_in_one_process_is_refused`).
