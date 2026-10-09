> This document describes the preceding 100-file checkpoint. See [current proposed release](CURRENT_RELEASE.md) for the 103-file Send repair and its distinct acceptance.

# Expanded release: exact source and reproduction

Accepted source inventory SHA256: `7c3ff877aca6982baf4469c1acef5b2be3930690f9a7f01857e5ce70d782d70c`. All 100 entries were checked before
and after copying. [Inventory](EXPANDED_SOURCE_MANIFEST.json) and
[sanitized acceptance](EXPANDED_VERIFICATION.json) bind the test claims to source bytes.
Dependencies, fixture and notices match the historical baseline; source additions and
changes are described by the staged publication diff. Documentation and screenshots
are separately hashed by the full publication manifest.

## Reproduce the typed flow

Follow the [README quick start](../README.md#quick-start). Dependencies remain pinned in
`requirements.lock` and `pyproject.toml`. Use a new `.expanded-demo-data` directory.
Schema migration 004 adds POI-source metadata. The older schema-3 application cannot
open a store upgraded to schema 4; do not point a historical checkout at that store.
No user database is shipped, and staging did not migrate any database.

Complete the three-step setup using an invented name. In Remember, type `My keys are
in the hall drawer`, inspect the parsed preview and press Send. In Chat ask
`where are my keys?`. Then try `move "My keys" to "desk"`: inspect the before/after
proposal and cancel or explicitly approve. Supported quoted commands are bounded
remember, move, rename, categorize and mark-location-unknown operations. They do not
use a general language model. A preview does not write; approval does.

Use the CC0 `tests/fixtures/vision/keys.jpg` to review photo item names/places yourself.
The browser suite confirmed two identities from one photo; it did not establish
automated visual identification. Saved records support dated evidence/history,
location correction, unknown location, recheck reminders and deletion.

## Optional nearby-place download

Default `APP_POI_DOWNLOAD_ENABLED=0` keeps source downloads disabled. An operator may
restart with `APP_POI_DOWNLOAD_ENABLED=1` and use the Nearby places UI. A download also
requires explicit confirmation and consent to share the manually entered area.
The fixed Overpass provider receives the bounding box and the connection IP address.
There is no automatic GPS capture. Area bounds use a 100–1000 m approximate halfwidth,
not a guaranteed coverage radius. One request is bounded to 1 MiB, 250 places and a
22-second deadline, with a 30-second attempt cooldown. Failure preserves the old cache.

Cached lookup works locally after download/import and uses straight-line distances
within the incomplete cache. Source age, missing places, stock, opening hours and routes
are unverified. Delete the cache or delete all to remove stored places. OSM data is
© OpenStreetMap contributors under ODbL; keep displayed attribution and the linked terms.
No OSM dataset is distributed in this package. One public-landmark request was accepted;
the offline/restart check used a Python socket guard, not OS-wide isolation.

## Optional voice and tests

[voice/SETUP.md](../voice/SETUP.md) and its corrected hash-pinned setup manifest describe
the Linux x86_64 / CPython 3.11 optional installer. An empty cache requires 820,069,956
payload bytes plus overhead and install space. Fixture tests passed; a real download,
fresh installation and current-UI speech flow have not passed acceptance. The document's
development-session download-budget note is historical context, not a runtime feature.
The older dependency inventory contains a partial PyTorch-wheel receipt; the corrected
full wheel hash is in `voice/setup-manifest.json`. Do not install from the old receipt.

Run README test commands only when the device is available. Browser tests require
Node/Playwright/Chromium with explicit `PLAYWRIGHT_MODULE`, `CHROMIUM_EXECUTABLE` and
`APP_TEST_PYTHON` paths. They create temporary synthetic stores and refresh evidence.
The real-source smoke script makes a network request; it is not part of the default
offline checks. `scripts/build_v1_archive.py` is a historical development exporter,
not a required installation step; it may reference private development reports omitted
from this sanitized distribution. This archive itself has hash/extraction verification,
not an extracted-archive runtime test pass.

Historical 335/54/335 evidence remains available with explicit baseline labels.
Current evidence is 408 backend tests, an overlapping 50-test targeted suite, 31 browser
checks and one real POI request. Do not add the overlapping test counts together.
