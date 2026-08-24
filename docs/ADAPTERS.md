# Publisher adapters

The public core intentionally stops at a completed, verified cache blob. A publisher
adapter can place that blob into a device-specific library and return the stable URI
that the renderer should play.

Configure a factory as `module:callable`:

```toml
[publisher]
factory = "my_private_adapter:create_publisher"
```

The factory is called as:

```python
publisher = create_publisher(settings=settings, cache=cache_store)
```

It must return an object with:

```python
def publish(entry: CacheEntry) -> str:
    """Publish an immutable blob and return a renderer-reachable media URI."""
```

`CacheEntry` contains the SHA-256 digest, local path, size, MIME type, irreversible
source fingerprint, and pin state. It never contains a source URL or credential.

An adapter must:

- treat the input blob as immutable;
- use an atomic or resumable copy and verify size/content before returning;
- return only a URI that the renderer can fetch;
- fail closed instead of silently returning the bridge stream URL;
- keep account or storage credentials outside the public configuration;
- redact URLs, credentials, media metadata, device identity, and topology from logs;
- provide its own tests, provenance, license, installation, and rollback procedure.

Adapters run as trusted code inside the daemon. Install only reviewed adapters and
grant the service account the minimum filesystem and network permissions they need.
