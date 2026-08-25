# Changelog

All notable changes to this project are documented in this file.

## 0.1.1 - 2026-08-25

- Scan every tracked Git index blob, including dotfiles, for high-confidence
  secrets, private IPv4 literals, and private or vendor brand residue.
- Add an isolated negative test proving that a secret in a tracked dotfile is
  rejected by the release audit.
- Replace GitLab CI with GitHub Actions across Python 3.11, 3.12, and 3.13.
- Use the package version as the single source for build metadata, runtime health,
  and HTTP server identification.

This maintenance release does not include private S26 deployment code, provider
credentials, account resolvers, or device-specific adapters.

## 0.1.0 - 2026-08-24

- Establish the initial vendor-neutral UPnP/OpenHome bridge, safe network streaming,
  content-addressed local cache, redacted health endpoint, packaging examples, tests,
  and Apache-2.0 release baseline.
