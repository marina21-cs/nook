# Real-photo vision fixtures and provenance

Rechecked 9 October 2026. These are public test photographs, not personal household records or a representative accuracy dataset. Original fixture bytes were not changed. Runtime tests read these local files and do not fetch photos or models.

## Sources, authors and license status

| Local fixture | Source and author | Photo license | Identity evidence |
| --- | --- | --- | --- |
| `coffee.png` | [scikit-image coffee](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.coffee), **Rachel Michetti**, courtesy of Pikolo Espresso Bar | CC0, explicitly stated by scikit-image | Local SHA256 matches the official v0.25.2 data registry |
| `chelsea.png` | [scikit-image Chelsea](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.chelsea), **Stefan van der Walt** | CC0, explicitly stated by scikit-image | Local SHA256 matches the official v0.25.2 data registry |
| `keys.jpg` | [Keys with pink background.JPG](https://commons.wikimedia.org/wiki/File:Keys_with_pink_background.JPG), **Eviatar Bach** / InverseHypercube | CC0 1.0, stated by the author on the file page | Local size/dimensions/SHA1 match Commons imageinfo, file page ID 18157629 |
| `scissors.jpg` | [Scissors - public domain 04.jpg](https://commons.wikimedia.org/wiki/File:Scissors_-_public_domain_04.jpg), **Oto Zapletal** | CC0 1.0, stated by the author on the file page | Local size/dimensions/SHA1 match the file page's structured metadata |
| `scissors-collection.jpg` | [Scissors collection.jpg](https://commons.wikimedia.org/wiki/File:Scissors_collection.jpg), **Becky Stern** / Bekathwia; [original Flickr post](https://www.flickr.com/photos/23243094@N00/6413733409/) | CC BY-SA 2.0; Commons records a Flickr license review | Local size/dimensions/SHA1 match the file page's structured metadata |

[CC0 1.0 deed](https://creativecommons.org/publicdomain/zero/1.0/); [CC BY-SA 2.0 deed](https://creativecommons.org/licenses/by-sa/2.0/). Licenses above apply to the photos, not the Commons page text/structured-data footer, scikit-image code, the model or the whole application. Original acquisition dates/commands were not preserved; verification here identifies existing bytes against upstream records rather than inventing their download history.

The official [scikit-image v0.25.2 registry](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/_registry.py) supplies the two PNG hashes; matching that registry does not imply this application installs scikit-image 0.25.2. The relevant photo license statements also remain in [skimage-fetchers.py.txt](../../../docs/vision-reference/skimage-fetchers.py.txt). Its exact upstream revision was not retained and could not be identified in the versions checked. Treat that reference-code provenance as unresolved; obtain the appropriate source license/notices and establish its version before packaging that copied code. It is not executed by the backend, and its code license must not be inferred from the photos' CC0 status.

## Exact fixture identity

[manifest.json](manifest.json) is the local SHA256/size inventory. All five entries were independently rehashed and matched. Pixel sizes are width × height.

| File | Bytes | Pixels | SHA256 |
| --- | ---: | --- | --- |
| `coffee.png` | 466,706 | 600 × 400 | `cc02f8ca188b167c775a7101b5d767d1e71792cf762c33d6fa15a4599b5a8de7` |
| `chelsea.png` | 240,512 | 451 × 300 | `596aa1e7cb875eb79f437e310381d26b338a81c2da23439704a73c4651e8c4bb` |
| `keys.jpg` | 5,097,723 | 4288 × 2848 | `a780e959480a21e29ed6cd75f42a343aab1d5e16371d4d9073af08111c64c22e` |
| `scissors.jpg` | 4,194,580 | 4000 × 3000 | `fa2f611c2cd3d6af808008c9853efa674d9c4c67e338a4c7f43ef7b1fd8316df` |
| `scissors-collection.jpg` | 3,042,095 | 4032 × 3024 | `fe70aa697d53d2ff1d9cb644f14d518b963e1a0d64f92ab4a51dd1ba5259140e` |

Commons publishes these matching SHA1 identifiers: keys `2369bc13c8c8f3944720743f93c5a04a049d5fa1`; single scissors `e25406151b4bfdd51dd70c4c0327c5dce3fdaf31`; collection `f15658813279c535847a5de9ee33ea65f150bf16`. SHA1 is used only to correlate Commons metadata with the existing files; the local inventory uses SHA256.

## Derivatives and attribution

`scripts/evaluate_vision.py` makes a uniform gray synthetic control, coffee blur (Gaussian radius 24), coffee darkening (brightness ×0.08), single-scissors reduction (32 × 24), and single-scissors 90° rotation. It caps derived images to 2048 pixels before encoding PNG. The app separately orients, strips metadata and re-encodes all uploaded evidence as JPEG. These transformations do not create ground-truth detection labels.

The existing `docs/vision-contact-sheet.jpg` resizes/annotates photographs. Attribution for its collection panel: **“Scissors collection” by Becky Stern, from Wikimedia Commons/Flickr, CC BY-SA 2.0; resized and annotated.** Preserve the credit, source/license links, change notice and applicable share-alike terms for that adapted photo contribution. No blanket license for the mixed contact sheet or whole project is asserted here. The original photos' metadata/date does not establish capture time of app-owned evidence or a present household location.

## Reproduce the existing checks

From the project root, using the already provisioned environment and [approved model](../../../models/README.md):

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib, json
root = Path('tests/fixtures/vision')
for name, expected in json.loads((root / 'manifest.json').read_text()).items():
    raw = (root / name).read_bytes()
    assert len(raw) == expected['bytes'], name
    assert hashlib.sha256(raw).hexdigest() == expected['sha256'], name
print('Five original fixtures verified')
PY
.venv/bin/python -m pytest tests/test_vision.py
.venv/bin/python -m scripts.smoke_api --vision --output /tmp/appbuilderhck-vision-smoke.json
.venv/bin/python -m scripts.evaluate_vision --output /tmp/appbuilderhck-vision-evaluation.json
```

These commands use local files and temporary synthetic records; HTTP smoke owns/stops its localhost server. The evaluation's five originals plus derivatives are the earlier convenience/tuning-inspection sample, not a held-out user-object dataset. Restoring a missing fixture is a deliberate provisioning action: use the exact source above, retain attribution, save under the local filename, then verify its manifest hash. Do not silently replace it with a thumbnail or a different photo. No new fixture download was needed for this provenance verification.

Misses, false labels and duplicates remain visible in [VISION_RESULTS.md](../../../docs/VISION_RESULTS.md). Unsupported keys and empty/degraded frames may yield no candidates; that never proves inventory absence. User confirmation/manual entry and evidence-grounded recall are tested separately from detector quality. No personal identity, shelf completeness, phone/camera behavior, correction-effort or general-object-understanding claim follows from these fixtures.

## Additional frozen challenge sample

The follow-up added [six new CC0 photos and a frozen 16-case challenge](heldout-20261009/README.md), independently hashed and labeled before detection. These are separate from the five original fixtures and their earlier convenience-sample evaluation. The new scripts use local files only; no runtime download path was added.
