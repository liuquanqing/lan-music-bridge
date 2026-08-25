# Compatibility

The automated suite verifies message construction and parsing with synthetic devices.
The implementation targets:

- SSDP M-SEARCH for UPnP MediaRenderer and OpenHome Source devices;
- OpenHome Product version 1 source selection when advertised, followed by Playlist
  version 1 actions used for clear, insert, seek, and transport;
- UPnP AVTransport version 1 fallback;
- HTTP/1.1 media delivery with a single byte range.

Real devices can vary in metadata requirements, service versions, multicast routing,
timeouts, and queue semantics. No model is certified by this repository. Compatibility
reports should contain only synthetic or redacted protocol evidence and the exact
software commit; never attach private media URLs, device identifiers, or topology.
