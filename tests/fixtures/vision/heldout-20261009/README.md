# Frozen held-out vision challenge, 9 October 2026

Six new CC0 public photographs were acquired explicitly for QA before inference, without changing any original fixture/model. Commons imageinfo size/SHA1 and EXIF-oriented dimensions were checked against the downloaded original bytes; local SHA256 inventory is in [provenance.json](provenance.json). No model download or runtime acquisition path was added.

| Fixture | Source and attribution | Bytes | Oriented pixels |
| --- | --- | ---: | --- |
| `plastic-cup.jpg` | [Image of plastic cup with yellow paper sleeve.jpg](https://commons.wikimedia.org/wiki/File:Image_of_plastic_cup_with_yellow_paper_sleeve.jpg), Magonayeon; CC0-1.0 | 2,306,454 | 2252 × 4000 |
| `v8-bottle.jpg` | [Bottle of V8 Power Blend Pineapple Passion.jpg](https://commons.wikimedia.org/wiki/File:Bottle_of_V8_Power_Blend_Pineapple_Passion.jpg), Brassluff; CC0-1.0 | 1,207,922 | 2448 × 3264 |
| `wooden-spoon-fork.jpg` | [Wooden Spoon and Fork 01.jpg](https://commons.wikimedia.org/wiki/File:Wooden_Spoon_and_Fork_01.jpg), PagesAndPathsPH; CC0-1.0 | 1,246,303 | 3456 × 3456 |
| `scissors-01.jpg` | [Scissors - public domain 01.jpg](https://commons.wikimedia.org/wiki/File:Scissors_-_public_domain_01.jpg), Oto Zapletal; CC0-1.0 | 4,188,838 | 4000 × 3000 |
| `museum-eyeglasses.jpg` | [Eyeglasses of Tomitaro Makino 2023-05-25.jpg](https://commons.wikimedia.org/wiki/File:Eyeglasses_of_Tomitaro_Makino_2023-05-25.jpg), Asanagi; CC0-1.0 | 794,714 | 2913 × 2185 |
| `museum-wallet.jpg` | [Wallet MET 51.96.6.jpg](https://commons.wikimedia.org/wiki/File:Wallet_MET_51.96.6.jpg), Metropolitan Museum of Art Open Access; individual photographer unspecified; CC0-1.0 | 86,052 | 728 × 552 |

[CC0 deed](https://creativecommons.org/publicdomain/zero/1.0/). Wallet source: [Met object 102715](https://www.metmuseum.org/art/collection/search/102715), accession 51.96.6. Scissors-01 shares the photographer/session of the original Scissors-04 fixture; it is a different photo, but not fully independent. Museum artifacts and staged cutlery are challenge cases, not typical modern drawer scenes.

[expected.json](expected.json) was saved before any inference at `2026-10-09T10:50:33.374153+00:00`; SHA256 `c19405bb0dcf2cce42b9c1d21b08d321cdbbbe8c3422d9b2286d447b820129ef`. It fixes six original frames, eight crops/blur/dark/bright/low-resolution variants and two synthetic empty controls. Target boxes are approximate manual annotations on oriented images. Target matching requires category and IoU ≥0.5, greedy one-to-one; overlapping extra same-class boxes count as duplicates. Unmatched context categories (people/laptop/chair/table for cup; background bottles/table for bottle) are reported separately, not treated as proof of correct full-scene inventory. Other boxes count as false positives or localization failures. Degraded frames may safely produce no suggestions, but missing a supported target still counts as a quality miss.

The evaluator applies deterministic PIL transforms, encodes metadata-free PNG, then uses the backend JPEG sanitizer and the unchanged worker API. It performs three requests per case and records every score/box/latency; random candidate IDs are excluded only from repeatability comparison. The 0.35 threshold, 0.6 NMS and approved model remain fixed. No post-result exclusions, new model, or accuracy-pass assertion.

Reproduce from the already provisioned project root:

```sh
.venv/bin/python -m scripts.qa_repeat_vision --output /tmp/appbuilderhck-heldout-vision.json
.venv/bin/python -m scripts.qa_repeat_http --output /tmp/appbuilderhck-http-repeat.json
```

Scripts use local assets, temporary synthetic records and process Python socket denial; the HTTP tool owns/stops port 18793 servers. No test-time downloads occur. The Python guard is not a native syscall trace or OS-wide isolation test. See [QA report](../../../../BACKEND_QA_REPORT.md) and [full vision results](../../../../docs/qa-repeat-vision.json).
