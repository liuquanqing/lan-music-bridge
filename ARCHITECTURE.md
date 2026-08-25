# Architecture

## Product boundary

LAN Music Bridge separates protocol control from source resolution and
device-specific storage:

```text
loopback CLI/admin API (single play or ordered queue)
        |
        v
orchestrator ---- SSDP discovery ---- renderer descriptions
    |                    |
    |                    +---- OpenHome Playlist / UPnP AVTransport SOAP
    |
    +---- stream registry ---- token URL ---- Range proxy ---- allow-listed source
    |
    +---- cache ---- SHA-256 blob + SQLite index ---- publisher adapter
                                                        |
                                                        +---- built-in bridge HTTP
                                                        +---- private device adapter
```

The core has no provider plugin interface, never imports a provider SDK, carries
account state, or assumes a specific renderer model. A user's external workflow can
supply a local file or allow-listed source URL to the core. A deployment can install a
trusted publisher adapter without changing protocol, cache, health, or logging behavior.

## Control path

Discovery sends bounded SSDP M-SEARCH requests. A response is accepted only when the
description URL resolves to the UDP responder. Description and SOAP bodies are capped
at 1 MiB. OpenHome Playlist is preferred; UPnP AVTransport is the fallback.

For one item, the controller selects the standard OpenHome `Playlist` Product source
when the Product service is available, then runs
`DeleteAll -> Insert -> SeekId -> Play`. The queue API accepts at most 100 items with
`mode`, `source`, `title`, and optional `content_type` fields. The runtime prepares
every item before device mutation. It then selects Playlist once and runs
`DeleteAll -> Insert... -> SeekId(first) -> Play`, chaining each returned OpenHome ID
to preserve order.

Play, queue, and transport mutations are serialized per renderer so concurrent
administration requests cannot interleave those steps.
The runtime assigns a per-renderer intent generation before media preparation. A
newer play, queue, or transport command supersedes any older request that has not
begun its renderer mutation, so slower cache or publisher work cannot restore an
obsolete target after the latest selection. Superseded and failed preparations discard
their stream tokens.

If Product source selection fails, queue mutation does not begin. Once `DeleteAll`
starts, OpenHome SOAP has no transaction or rollback primitive; a later failure is
reported as a possibly partial device queue, and prepared token URLs retain their
normal six-hour lifetime in case the renderer already references them. UPnP uses
`SetAVTransportURI -> Play` for one item. AVTransport has no standard multi-track queue
operation, so the queue API rejects those renderers instead of claiming continuity.
The controller returns only a protocol receipt; it does not persist renderer names,
addresses, queue metadata, titles, or source URLs.

## Streaming path

The daemon validates the source scheme, exact host allow-list, and every DNS answer.
It then creates a random in-memory token. The renderer receives only the bridge token
URL. Each upstream connection is pinned to an already validated address, redirects
are rejected, and TLS certificates are checked against the original host name.

## Local cache path

Downloads and local-file ingests are streamed into a private temporary file while a
SHA-256 digest is computed. When an upstream declares `Content-Length`, the received
length must match exactly before the blob is published. Without a declared length,
the digest covers the bytes actually received but cannot establish the upstream's
intended total. The file is fsynced and atomically renamed into an immutable blob path.
SQLite stores only digest, size, MIME type, timestamps, pin state, and an irreversible
source fingerprint. Raw URLs are never persisted. The storage layer exposes a pin
method internally, but no CLI or administration API currently makes it a user feature.

The default publisher exposes `/media/<sha256>` with single-range support. An adapter
may instead copy the completed blob to a renderer library and return its indexed URI.
The adapter never receives credentials from the core; any private credentials remain
owned by that separately installed deployment layer.

## Health and logs

`/health` reports version, uptime, cache counts, active stream-token count, and the
last protocol family; `/ready` reports readiness. Both are unauthenticated on the
media listener and are intended only for trusted LANs. They omit device identity, IP
addresses, titles, URLs, queue state, headers, and credentials. The administration
listener remains loopback-only. Structured logs replace HTTP peer addresses with
irreversible short fingerprints and apply key-based and URL-shaped value redaction
before serialization.
