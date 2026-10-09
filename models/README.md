# Installed local NanoDet model

Provenance rechecked 9 October 2026. This file documents the existing weights; no model or package was downloaded or changed during this documentation task.

| Property | Verified value |
| --- | --- |
| Publisher/source | OpenCV model collection, `opencv/object_detection_nanodet` |
| Architecture | NanoDet-m-plus-1.5x_416 |
| File/export | `object_detection_nanodet_2022nov.onnx`, original non-int8 export |
| Pinned repository revision | `81a2a35b00f92e9bd03f03d9b611076d9aa2f942` |
| Exact bytes | 3,800,954 |
| SHA256 | `4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186` |
| Runtime tested here | Python 3.11.15, OpenCV headless 4.13.0.92, NumPy 2.2.6 |

The [official commit's LFS pointer](https://huggingface.co/opencv/object_detection_nanodet/commit/81a2a35b00f92e9bd03f03d9b611076d9aa2f942) publishes the same hash and byte count. The [pinned model card](https://huggingface.co/opencv/object_detection_nanodet/blob/81a2a35b00f92e9bd03f03d9b611076d9aa2f942/README.md) identifies this architecture and states Apache-2.0 for the directory's files, including weights. Its raw text was independently fetched at that revision. [Pinned weight source](https://huggingface.co/opencv/object_detection_nanodet/resolve/81a2a35b00f92e9bd03f03d9b611076d9aa2f942/object_detection_nanodet_2022nov.onnx).

## License and attribution

The existing [LICENSE](LICENSE) is byte-identical to the [pinned upstream license](https://huggingface.co/opencv/object_detection_nanodet/raw/81a2a35b00f92e9bd03f03d9b611076d9aa2f942/LICENSE); SHA256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`. The model card credits **Sri Siddarth Chakaravarthy**, OpenCV, Google Summer of Code 2022, and references **RangiLyu/NanoDet** for training weights/scripts. [NanoDet upstream](https://github.com/RangiLyu/nanodet).

The application's reviewed preprocessing/postprocessing is adapted from OpenCV Zoo's reference. Reference copies and Apache license are retained in [docs/vision-reference](../docs/vision-reference); `app/inference/nanodet.py` carries the adaptation notice. Their original download log/exact reference-code commit was not retained, so this document does not assert one. These reference files are not executed by the app.

Preserve applicable upstream license, attribution, modification notices and any upstream NOTICE supplied with a distribution. The model's license does not license fixture photos, application data or every bundled dependency. See [dependency disclosure](../docs/DEPENDENCIES_AND_MODELS.md) and the [fixture README](../tests/fixtures/vision/README.md). This document is provenance evidence, not certification of an entire redistribution package.

## Provisioning and verification

The present project already contains the verified model. Weights are excluded from Git by `models/*.onnx`, so a fresh source checkout may lack them. Provisioning is a separate, deliberate operator step: obtain the exact pinned artifact from the source above or an already verified local copy; place the regular file at `models/object_detection_nanodet_2022nov.onnx`; retain its license; verify the byte count and hash below before starting. Do not use the similarly named int8/int8bq files or a Git LFS text pointer. This review did not perform a new download or test a clean-checkout install.

From the project root, with the documented local environment installed:

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
path = Path('models/object_detection_nanodet_2022nov.onnx')
assert path.is_file() and not path.is_symlink()
raw = path.read_bytes()
assert len(raw) == 3800954
assert hashlib.sha256(raw).hexdigest() == '4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186'
print('Exact approved local model verified')
PY
```

Normal configuration selects this bundled file. An explicit local override requires both `APP_VISION_MODEL` and `APP_VISION_SHA256`, and still accepts only this approved hash. `APP_VISION_DISABLED=1` chooses manual confirmation. Missing, altered, unapproved or symlink weights fail closed and preserve the draft/manual path. [Backend startup and tests](../BACKEND_README.md).

## Runtime and limitations

Local CPU inference uses 416 × 416 RGB letterboxing, two CPU threads, OpenCL disabled, threshold 0.35, class-aware NMS IoU 0.6, at most 20 candidates, and an isolated worker with timeout/cancellation. No threshold or model change is made by this documentation. The app and evaluation tools read pre-provisioned local weights/fixtures and contain no runtime fetch/install path; reviewed code and guarded HTTP runs support that statement. Worker Python socket/DNS denial is not OS-wide network isolation. Existing optional text normalization is a separate fixed-loopback dependency.

The 80 COCO categories do not identify personal belongings or locations. Keys, chargers, wallets and eyeglasses require manual entry. Misses, duplicate boxes and wrong classes are documented in [VISION_RESULTS.md](../docs/VISION_RESULTS.md). Every saved identity/location needs explicit user review and confirmation. Laptop execution does not establish phone/GPU performance, general visual reasoning or useful accuracy on a user's actual drawer scenes.
