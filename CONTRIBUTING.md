# Contributing

Contributions should keep the core vendor-neutral and preserve the security boundary
between public protocol/cache code and private provider or device adapters.

Before submitting a merge request:

1. add or update unit tests;
2. run `make check` and `make release-audit`;
3. update architecture or security documentation when a boundary changes;
4. confirm every new file's source and license in `PROVENANCE.md` or `NOTICE`;
5. avoid real addresses, device names, media metadata, credentials, cookies, and URLs;
6. use synthetic RFC 5737 addresses and example domains in tests and docs.

Commits must be reviewable and should not include generated wheels, bytecode, media,
firmware, packet captures, or runtime databases. New dependencies require a license,
maintenance, and supply-chain review before adoption.
