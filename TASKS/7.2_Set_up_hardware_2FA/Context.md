# LLM Agent Context Log

## 2026-10-13: Keys ordered

* Wayne ordered two Yubico Security Keys (FIDO2), arriving 2026-10-14.
* This machine (Ubuntu 24.04) already has `libfido2` and udev's
  `60-fido-id.rules`, so browsers should see a key when plugged in.
  If a browser ignores the key's touch, a udev rule is the first suspect.
* Start here when they arrive, one site at a time, both keys on each:
  1. GitHub (Settings -> Password and authentication -> Security keys),
     first, since it becomes the publishing gate under `T.wrw`.
  2. pypi.org: new account, verify the email, Account settings -> Two
     factor authentication -> add a security device; save the recovery
     codes.
  3. test.pypi.org: a separate account, same steps, same username if
     free.
  4. Everywhere: an authenticator app as fallback, recovery codes kept
     offline, the backup key stored apart from the primary.
* No API token on either PyPI; Trusted Publishing (`T.wrw`) replaces it.
* Offered while waiting: start `T.wrw` (build script around
  `release_wheel`, `release.yml`), which needs no account.
