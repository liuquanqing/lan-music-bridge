# Architecture

## Product boundary

LAN Music Bridge separates protocol control from source resolution and
device-specific storage:

```text
loopback CLI/admin API
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

The core never imports a provider SDK, carries account state, or assumes a specific
renderer model. A deployment can supply a source URL to the core or install a trusted
publisher adapter without changing protocol, cache, health, or logging behavior.

## Control path

Discovery sends bounded SSDP M-SEARCH requests. A response is accepted only when the
description URL resolves to the UDP responder. Description and SOAP bodies are capped
at 1 MiB. OpenHome Playlist is preferred; UPnP AVTransport is the fallback.

For a new item, the controller selects the standard OpenHome `Playlist` Product
source when the Product service is available, then runs
`DeleteAll -> Insert -> SeekId -> Play`. Play and transport mutations are serialized
per renderer so concurrent administration requests cannot interleave those steps.
The runtime assigns a per-renderer intent generation before media preparation. A
newer play or transport command supersedes any older request that has not begun its
renderer mutation, so slower cache or publisher work cannot restore an obsolete
target after the latest selection.
If Product source selection fails, queue mutation does not begin. UPnP uses
`SetAVTransportURI -> Play`. The controller returns only a protocol receipt; it does
not persist renderer names, addresses, queue metadata, or source URLs.

## Streaming path

The daemon validates the source scheme, exact host allow-list, and every DNS answer.
It then creates a random in-memory token. The renderer receives only the bridge token
URL. Each upstream connection is pinned to an already validated address, redirects
are rejected, and TLS certificates are checked against the original host name.

## Local cache path

Downloads and local-file ingests are streamed into a private temporary file while a
SHA-256 digest is computed. The file is fsynced and atomically renamed into an
immutable blob path. SQLite stores only digest, size, MIME type, timestamps, pin state,
and an irreversible source fingerprint. Raw URLs are never persisted.

The default publisher exposes `/media/<sha256>` with single-range support. An adapter
may instead copy the completed blob to a renderer library and return its indexed URI.
The adapter never receives credentials from the core; any private credentials remain
owned by that separately installed deployment layer.

## Health and logs

`/health` reports version, uptime, cache counts, active stream-token count, and the
last protocol family. It omits device identity, IP addresses, titles, URLs, queue
state, headers, and credentials. Structured logs apply key-based and URL-shaped value
redaction before serialization.
