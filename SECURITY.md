# Security policy

## Supported versions

Security fixes are provided for the latest tagged version and the default branch.
This initial version is an alpha release candidate; deploy it on a segmented trusted
LAN and keep a rollback path.

## Reporting a vulnerability

Use the GitHub repository's private vulnerability-reporting channel when available.
Do not include credentials, cookies, signed URLs, device identifiers, private media,
or complete household topology in an issue. A minimal redacted reproduction and the
exact commit SHA are sufficient to begin triage.

## Security properties

- The administration API refuses non-loopback clients and configuration validation
  rejects non-loopback admin binds.
- Sources require an exact host allow-list. All DNS answers are checked; private,
  loopback, link-local, multicast, reserved, and unspecified addresses are rejected
  unless private sources are explicitly enabled.
- Upstream connections are pinned to validated addresses, redirects are rejected,
  and HTTPS retains hostname certificate validation.
- Stream URLs are held only in memory behind random tokens and expire after six hours.
- Cache records persist fingerprints rather than raw source URLs.
- Health and ordinary logs omit URLs, headers, queue metadata, device addresses, and
  identities. Error responses are deliberately generic.
- Downloads are size-capped, written atomically, and content-addressed.

## Deployment responsibilities

The media server has no user authentication or TLS. Restrict it with the host firewall
to renderer networks that need it. A SHA-256 media path is not an authorization token.
Cache storage is not encrypted by this application; use encrypted storage when media
confidentiality at rest matters.

Setting `allow_private = true` allows an allow-listed source to resolve into private
address space. Use it only for a known internal media service, and restrict the exact
host list. Publisher adapters execute as trusted code with the service account's file
and network permissions; audit them independently.

SSDP and SOAP devices are untrusted network peers. Keep discovery timeouts bounded and
do not run the daemon with root privileges. The supplied service units use a dedicated
account and filesystem protections.

## Secret handling

Never place source account credentials, cookies, signed URLs, or private keys in the
repository or TOML file. Feed ephemeral URLs through CLI stdin. Store adapter secrets
outside the repository with mode `0600`, and have the private adapter read them at
runtime. Before any public push, run `make release-audit` and inspect the exact staged
tree.
