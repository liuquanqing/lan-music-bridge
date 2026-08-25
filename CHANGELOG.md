# Changelog

All notable changes to this project are documented in this file.

## 0.3.0 - Unreleased

- Shorten the bilingual README and foreground local-playback quality and stable delivery.
- Make renderer intent last-target-wins across media preparation: a newer play or
  transport command supersedes any older request that has not started its renderer
  mutation.
- Reject a downloaded cache candidate when a declared `Content-Length` does not match
  the received byte count, before publishing a blob.
- Replace raw HTTP peer addresses in structured access logs with irreversible short
  fingerprints.
- Add CLI `play --content-type` passthrough for renderers that require an explicit MIME
  declaration; retain `audio/mpeg` for streams and extension inference for local files.
- Reframe the bilingual README around deployment on an always-on router or Linux
  gateway, with device-local publication as the recommended adapter path and
  UPnP/OpenHome streaming as the immediate compatibility path.
- State the quality boundary explicitly: declared-length validation,
  content-addressing of received bytes, and no implicit transcoding are verifiable,
  but caching alone does not promise better sound.
- Document that the core has no provider plugin or quality contract, pinning has no
  CLI/API, stream tokens default to six hours, and media health/readiness endpoints are
  unauthenticated on trusted LANs.
- Keep device queue/prefetch generations, output-event reconciliation, and concrete
  device-library import outside the public core.

## 0.2.0 - 2026-08-25

- Make the GitHub landing README bilingual, with Simplified Chinese displayed first
  and the complete English introduction retained on the same page.
- Select the standard OpenHome `Playlist` Product source before replacing its
  queue when a renderer exposes the Product service.
- Serialize play and transport mutations per renderer so concurrent administration
  requests cannot interleave queue replacement steps.
- Leave the existing playlist untouched when Product source selection fails.
- Keep provider resolution, device-specific queue modes, multi-listener controller
  facades, and GENA subscription lifecycles outside the public core until they have
  a vendor-neutral product surface.
- Use the package version in the SOAP `User-Agent` header.

## 0.1.1 - 2026-08-25

- Scan every tracked Git index blob, including dotfiles, for high-confidence
  secrets, private IPv4 literals, and private or vendor brand residue.
- Add an isolated negative test proving that a secret in a tracked dotfile is
  rejected by the release audit.
- Replace GitLab CI with GitHub Actions across Python 3.11, 3.12, and 3.13.
- Use the package version as the single source for build metadata, runtime health,
  and HTTP server identification.

This maintenance release does not include private deployment code, provider
credentials, account resolvers, or device-specific adapters.

## 0.1.0 - 2026-08-24

- Establish the initial vendor-neutral UPnP/OpenHome bridge, safe network streaming,
  content-addressed local cache, redacted health endpoint, packaging examples, tests,
  and Apache-2.0 release baseline.
