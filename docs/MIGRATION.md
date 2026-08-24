# Private deployment boundary

This repository is a clean, portable product core. A private router deployment should
remain a separate layer that owns:

- real interfaces, addresses, VLANs, and firewall rules;
- provider account state, cookies, tokens, and source resolvers;
- device-specific storage mounts, indexing behavior, and publisher adapters;
- renderer identities selected for production;
- runtime state, media, backups, and rollback receipts.

Migration should be staged:

1. install the public core without enabling it;
2. install a reviewed private adapter outside the public repository;
3. write a local configuration from the example without copying old runtime state;
4. validate config, service account permissions, source allow-list, and firewall;
5. run discovery and read-only description/control probes;
6. stop or isolate the previous publisher before enabling duplicate identities;
7. test one synthetic/local file, one allow-listed stream, pause/stop, restart, upgrade,
   and rollback;
8. record the exact package version and commit SHA in the private deployment ledger.

Do not interpret public unit-test success as proof of compatibility with a particular
renderer or topology. Device-local publication remains unverified until its private
adapter passes copy, indexing, URI, playback, cancellation, capacity, and rollback
tests on the intended hardware.
