"""Reviewed NanoDet CPU inference, derived from OpenCV Zoo's Apache-2.0 reference.

See docs/vision-reference/LICENSE and models/README.md for provenance. No camera,
URL input, downloads, OCR, personal identity inference or location inference.
"""

from typing import Any

MODEL_ID = "opencv/nanodet-m-plus-1.5x_416/2022nov"
MODEL_SHA256 = "4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186"
MODEL_BYTES = 3_800_954
MODEL_FILENAME = "object_detection_nanodet_2022nov.onnx"
OPENCV_VERSION = "4.13.0.92"
NUMPY_VERSION = "2.2.6"
CONFIDENCE = 0.35
NMS_IOU = 0.6
STRIDES = (8, 16, 32)  # This pinned ONNX exports three heads, six output tensors.
CLASSES = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)


class NanoDet:
    def __init__(self, verified_model: bytes) -> None:
        import cv2
        import numpy as np

        self.cv: Any = cv2
        self.np: Any = np
        cv2.setNumThreads(2)
        cv2.ocl.setUseOpenCL(False)
        self.net = cv2.dnn.readNetFromONNX(np.frombuffer(verified_model, dtype=np.uint8))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.mean = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
        self.std = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)
        self.anchors: list[Any] = []
        for stride in STRIDES:
            side = 416 // stride
            xv, yv = np.meshgrid(np.arange(side) * stride, np.arange(side) * stride)
            self.anchors.append(np.column_stack((xv.flatten(), yv.flatten())) + 0.5 * (stride - 1))

    def letterbox(self, rgb: Any) -> tuple[Any, tuple[int, int, int, int]]:
        height, width = rgb.shape[:2]
        if height <= 0 or width <= 0 or rgb.shape != (height, width, 3):
            raise ValueError("RGB image required")
        # Match the reviewed reference's floor rounding, black padding and RGB order.
        new_h = max(1, int(416 * min(1, height / width)))
        new_w = max(1, int(416 * min(1, width / height)))
        top, left = (416 - new_h) // 2, (416 - new_w) // 2
        resized = self.cv.resize(rgb, (new_w, new_h), interpolation=self.cv.INTER_AREA)
        padded = self.cv.copyMakeBorder(
            resized,
            top,
            416 - new_h - top,
            left,
            416 - new_w - left,
            self.cv.BORDER_CONSTANT,
            value=0,
        )
        return padded, (top, left, new_h, new_w)

    def infer(self, rgb: Any, confidence: float = CONFIDENCE) -> list[dict[str, Any]]:
        if not 0 < confidence < 1:
            raise ValueError("Confidence must be between zero and one")
        np = self.np
        padded, transform = self.letterbox(rgb)
        normalized = (padded.astype(np.float32) - self.mean) / self.std
        self.net.setInput(self.cv.dnn.blobFromImage(normalized))
        outputs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        rows = self.decode(outputs, confidence)
        height, width = rgb.shape[:2]
        top, left, new_h, new_w = transform
        results = []
        for box, score, class_id in rows:
            region = self.map_region(box, transform, (width, height))
            if region is None:
                continue
            results.append(
                {
                    "category": CLASSES[class_id],
                    "score": float(score),
                    "region": region,
                }
            )
            if len(results) == 20:
                break
        return results

    def map_region(
        self, box: Any, transform: tuple[int, int, int, int], size: tuple[int, int]
    ) -> dict[str, float] | None:
        top, left, new_h, new_w = transform
        width, height = size
        x1, x2 = self.np.clip((box[[0, 2]] - left) / new_w, 0, 1)
        y1, y2 = self.np.clip((box[[1, 3]] - top) / new_h, 0, 1)
        if (x2 - x1) * width < 1 or (y2 - y1) * height < 1:
            return None  # Padding-only/degenerate boxes do not describe evidence.
        return {"x": float(x1), "y": float(y1), "w": float(x2 - x1), "h": float(y2 - y1)}

    def decode(self, outputs: Any, confidence: float) -> list[tuple[Any, float, int]]:
        np = self.np
        if len(outputs) != 6:
            raise ValueError("Unexpected model output count")
        all_boxes, all_scores = [], []
        for index, stride in enumerate(STRIDES):
            anchors = self.anchors[index]
            scores = np.asarray(outputs[2 * index])
            regression = np.asarray(outputs[2 * index + 1])
            if scores.shape != (1, len(anchors), 80) or regression.shape != (1, len(anchors), 32):
                raise ValueError("Unexpected model output dimensions")
            scores, regression = scores[0], regression[0]
            if not np.isfinite(scores).all() or not np.isfinite(regression).all():
                raise ValueError("Non-finite model output")
            if np.any(scores < 0) or np.any(scores > 1):
                raise ValueError("Invalid score range")
            distribution = regression.reshape(-1, 8)
            distribution = np.exp(distribution - distribution.max(axis=1, keepdims=True))
            distribution /= distribution.sum(axis=1, keepdims=True)
            distance = (distribution @ np.arange(8)).reshape(-1, 4) * stride
            if len(scores) > 1000:
                selected = scores.max(axis=1).argsort()[::-1][:1000]
                anchors, distance, scores = anchors[selected], distance[selected], scores[selected]
            boxes = np.column_stack(
                (
                    anchors[:, 0] - distance[:, 0],
                    anchors[:, 1] - distance[:, 1],
                    anchors[:, 0] + distance[:, 2],
                    anchors[:, 1] + distance[:, 3],
                )
            )
            all_boxes.append(np.clip(boxes, 0, 416))
            all_scores.append(scores)
        boxes, scores = np.concatenate(all_boxes), np.concatenate(all_scores)
        class_ids, confidences = scores.argmax(axis=1), scores.max(axis=1)
        wh = boxes.copy()
        wh[:, 2:4] -= wh[:, 0:2]
        # Class-aware suppression preserves overlapping objects of different categories.
        kept = self.cv.dnn.NMSBoxesBatched(
            wh.tolist(), confidences.tolist(), class_ids.tolist(), confidence, NMS_IOU
        )
        indexes = sorted(np.asarray(kept).flatten().tolist(), key=lambda i: -confidences[i])
        return [(boxes[i], float(confidences[i]), int(class_ids[i])) for i in indexes]
