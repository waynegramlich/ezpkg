# 7.3 Write the release workflow

A GitHub Actions workflow that publishes with Trusted Publishing, the
same for test.pypi.org (`T.utt`) and pypi.org (`T.utp`) except for the
target and the environment:

* A build script around `release_wheel` in `ezpkg_test.py`; no
  `pyproject.toml`, and no sdist.
* `.github/workflows/release.yml`, fired by a tag that Wayne pushes,
  refusing a tag that does not match `__version__`.
* GitHub environments `testpypi` and `pypi`, each needing Wayne's
  approval before the upload.
