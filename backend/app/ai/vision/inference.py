from __future__ import annotations

from abc import ABC, abstractmethod
import ast
import hashlib
import io
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_DIR, REPO_ROOT, Settings

from .types import InferenceBox, InferenceDetection, InferenceResult

logger = logging.getLogger("app.ai.vision.inference")


class VisionInferenceEngine(ABC):
    @abstractmethod
    def infer(self, image_bytes: bytes) -> InferenceResult:
        raise NotImplementedError

    @abstractmethod
    def runtime_status(self) -> dict[str, Any]:
        raise NotImplementedError


class MockInferenceEngine(VisionInferenceEngine):
    def __init__(self, mode: str):
        self._mode = mode

    def infer(self, image_bytes: bytes) -> InferenceResult:
        digest = hashlib.sha256(image_bytes).digest()
        labels = ["leaf_spot", "powdery_mildew", "blight", "healthy_leaf"]
        label = labels[digest[0] % len(labels)]
        confidence = 0.55 + (digest[1] % 35) / 100
        base_x = float(20 + digest[2] % 120)
        base_y = float(20 + digest[3] % 120)
        width = float(40 + digest[4] % 100)
        height = float(40 + digest[5] % 100)
        detection = InferenceDetection(
            label=label,
            confidence=min(confidence, 0.97),
            bbox=InferenceBox(
                x1=base_x,
                y1=base_y,
                x2=base_x + width,
                y2=base_y + height,
            ),
        )
        return InferenceResult(
            detections=[detection],
            engine="mock",
            device="cpu",
            fallback_occurred=False,
        )

    def runtime_status(self) -> dict[str, Any]:
        return {
            "mode": self._mode,
            "engine": "mock",
            "preferredDevice": "cpu",
            "activeDevice": "cpu",
            "fallbackOccurred": False,
        }


class YoloInferenceEngine(VisionInferenceEngine):
    def __init__(self, settings: Settings, mode: str):
        self._mode = mode
        self._model_path = settings.vision_model_path
        self._confidence_threshold = settings.vision_confidence_threshold
        self._model = None
        self._preferred_device = self._detect_preferred_device()
        self._active_device = self._preferred_device
        self._fallback_occurred = False
        self._yolo_cls = self._load_yolo_cls()

    def infer(self, image_bytes: bytes) -> InferenceResult:
        model = self._get_model()
        image = self._decode_image(image_bytes)

        try:
            return self._run_predict(model, image, self._preferred_device, fallback=False)
        except Exception as exc:
            if self._preferred_device != "mps":
                raise
            logger.warning("YOLO inference on MPS failed, falling back to CPU: %s", exc)
            return self._run_predict(model, image, "cpu", fallback=True)

    def runtime_status(self) -> dict[str, Any]:
        return {
            "mode": self._mode,
            "engine": "yolo",
            "preferredDevice": self._preferred_device,
            "activeDevice": self._active_device,
            "fallbackOccurred": self._fallback_occurred,
        }

    def _load_yolo_cls(self):
        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - dependency presence is runtime-dependent.
            raise RuntimeError("ultralytics is required for YOLO inference mode.") from exc
        return YOLO

    def _get_model(self):
        if self._model is None:
            self._model = self._yolo_cls(self._model_path)
        return self._model

    def _detect_preferred_device(self) -> str:
        try:
            import torch
        except Exception:
            return "cpu"

        try:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            return "cpu"
        return "cpu"

    def _decode_image(self, image_bytes: bytes):
        try:
            from PIL import Image
            import numpy as np
        except Exception as exc:  # pragma: no cover - dependency presence is runtime-dependent.
            raise RuntimeError("Pillow and numpy are required for YOLO inference mode.") from exc

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(image)

    def _run_predict(self, model, image, device: str, fallback: bool) -> InferenceResult:
        results = model.predict(
            source=image,
            conf=self._confidence_threshold,
            device=device,
            verbose=False,
        )
        detections: list[InferenceDetection] = []
        for result in results:
            names = result.names if isinstance(result.names, dict) else {}
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_idx = int(float(box.cls[0])) if box.cls is not None else -1
                label = names.get(cls_idx, f"class_{cls_idx}")
                confidence = float(box.conf[0]) if box.conf is not None else 0.0
                bbox = None
                xyxy = box.xyxy[0].tolist() if box.xyxy is not None else None
                if xyxy and len(xyxy) == 4:
                    bbox = InferenceBox(
                        x1=float(xyxy[0]),
                        y1=float(xyxy[1]),
                        x2=float(xyxy[2]),
                        y2=float(xyxy[3]),
                    )
                detections.append(
                    InferenceDetection(
                        label=label,
                        confidence=confidence,
                        bbox=bbox,
                    )
                )

        self._active_device = device
        self._fallback_occurred = fallback
        return InferenceResult(
            detections=detections,
            engine="yolo",
            device=device,
            fallback_occurred=fallback,
        )


class OnnxInferenceEngine(VisionInferenceEngine):
    def __init__(self, settings: Settings, mode: str):
        self._mode = mode
        self._model_path = settings.vision_model_path
        self._confidence_threshold = settings.vision_confidence_threshold
        self._nms_iou_threshold = settings.vision_nms_iou_threshold
        self._configured_class_names = self._parse_configured_class_names(settings.vision_class_names)
        self._session = None
        self._preferred_device = "cpu"
        self._active_device = "cpu"
        self._input_name = ""
        self._input_width = 640
        self._input_height = 640
        self._class_names: list[str] = []

    def infer(self, image_bytes: bytes) -> InferenceResult:
        session = self._get_session()
        image, meta = self._preprocess(image_bytes)
        outputs = session.run(None, {self._input_name: image})
        detections = self._postprocess(outputs, meta)
        return InferenceResult(
            detections=detections,
            engine="onnx",
            device=self._active_device,
            fallback_occurred=False,
        )

    def runtime_status(self) -> dict[str, Any]:
        return {
            "mode": self._mode,
            "engine": "onnx",
            "preferredDevice": self._preferred_device,
            "activeDevice": self._active_device,
            "fallbackOccurred": False,
        }

    def _load_onnxruntime(self):
        try:
            import onnxruntime as ort
        except Exception as exc:
            raise RuntimeError("onnxruntime is required for ONNX inference mode.") from exc
        return ort

    def _get_session(self):
        if self._session is not None:
            return self._session

        model_path, tried_paths = self._resolve_model_path(self._model_path)
        if not model_path.exists():
            tried = ", ".join(str(path) for path in tried_paths)
            raise RuntimeError(f"ONNX model file not found: {self._model_path}. Tried: {tried}")

        ort = self._load_onnxruntime()
        providers = self._select_providers(ort)
        self._session = ort.InferenceSession(str(model_path), providers=providers)
        self._active_device = self._preferred_device

        input_meta = self._session.get_inputs()[0]
        self._input_name = input_meta.name
        if len(input_meta.shape) != 4:
            raise RuntimeError(f"Unsupported ONNX input shape: {input_meta.shape}")

        self._input_height = self._safe_dim(input_meta.shape[2], 640)
        self._input_width = self._safe_dim(input_meta.shape[3], 640)
        self._class_names = self._load_class_names(self._session)
        return self._session

    @staticmethod
    def _resolve_model_path(raw_path: str) -> tuple[Path, list[Path]]:
        raw = Path(raw_path).expanduser()
        tried: list[Path] = []
        if raw.is_absolute():
            absolute = raw.resolve()
            return absolute, [absolute]

        # Support launching from repo root or backend directory with the same env value.
        candidates = [
            (REPO_ROOT / raw).resolve(),
            (BACKEND_DIR / raw).resolve(),
            (Path.cwd() / raw).resolve(),
        ]
        for candidate in candidates:
            tried.append(candidate)
            if candidate.exists():
                return candidate, tried
        return candidates[0], tried

    def _select_providers(self, ort) -> list[str]:
        available = ort.get_available_providers()
        if "CoreMLExecutionProvider" in available:
            self._preferred_device = "coreml"
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        self._preferred_device = "cpu"
        if "CPUExecutionProvider" in available:
            return ["CPUExecutionProvider"]
        return list(available)

    def _load_class_names(self, session) -> list[str]:
        if self._configured_class_names:
            return self._configured_class_names

        metadata = session.get_modelmeta().custom_metadata_map or {}
        raw_names = metadata.get("names")
        if not raw_names:
            return []

        parsed = None
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw_names)
                break
            except Exception:
                continue
        if parsed is None:
            return []

        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if isinstance(parsed, dict):
            items: list[tuple[int, str]] = []
            for key, value in parsed.items():
                try:
                    idx = int(key)
                except Exception:
                    continue
                items.append((idx, str(value)))
            return [value for _, value in sorted(items, key=lambda item: item[0])]
        return []

    @staticmethod
    def _parse_configured_class_names(raw: str) -> list[str]:
        names = [item.strip() for item in (raw or "").split(",")]
        return [name for name in names if name]

    @staticmethod
    def _safe_dim(value: Any, default: int) -> int:
        if isinstance(value, int) and value > 0:
            return value
        return default

    def _decode_image(self, image_bytes: bytes):
        try:
            from PIL import Image
            import numpy as np
        except Exception as exc:
            raise RuntimeError("Pillow and numpy are required for ONNX inference mode.") from exc

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(image)

    def _preprocess(self, image_bytes: bytes):
        import numpy as np
        from PIL import Image

        original = self._decode_image(image_bytes)
        orig_h, orig_w = original.shape[:2]
        scale = min(self._input_width / orig_w, self._input_height / orig_h)
        resized_w = max(1, int(round(orig_w * scale)))
        resized_h = max(1, int(round(orig_h * scale)))

        resized = np.array(Image.fromarray(original).resize((resized_w, resized_h), Image.BILINEAR))
        canvas = np.full((self._input_height, self._input_width, 3), 114, dtype=np.uint8)
        pad_x = (self._input_width - resized_w) // 2
        pad_y = (self._input_height - resized_h) // 2
        canvas[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized

        image = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        meta = {
            "orig_w": float(orig_w),
            "orig_h": float(orig_h),
            "scale": float(scale),
            "pad_x": float(pad_x),
            "pad_y": float(pad_y),
            "input_w": float(self._input_width),
            "input_h": float(self._input_height),
        }
        return image, meta

    def _postprocess(self, outputs: list[Any], meta: dict[str, float]) -> list[InferenceDetection]:
        import numpy as np

        predictions = self._normalize_predictions(outputs)
        if predictions.size == 0:
            return []

        candidate_boxes: list[list[float]] = []
        candidate_scores: list[float] = []
        candidate_classes: list[int] = []

        for row in predictions:
            decoded = self._decode_prediction(row)
            if decoded is None:
                continue
            box, confidence, class_id = decoded
            if confidence < self._confidence_threshold:
                continue

            x1, y1, x2, y2 = self._box_to_xyxy(box, meta)
            if x2 <= x1 or y2 <= y1:
                continue
            candidate_boxes.append([x1, y1, x2, y2])
            candidate_scores.append(float(confidence))
            candidate_classes.append(int(class_id))

        if not candidate_boxes:
            return []

        selected = self._nms(candidate_boxes, candidate_scores, self._nms_iou_threshold)
        detections: list[InferenceDetection] = []
        for idx in selected:
            class_id = candidate_classes[idx]
            if 0 <= class_id < len(self._class_names):
                label = self._class_names[class_id]
            else:
                label = f"class_{class_id}"
            x1, y1, x2, y2 = candidate_boxes[idx]
            detections.append(
                InferenceDetection(
                    label=label,
                    confidence=candidate_scores[idx],
                    bbox=InferenceBox(x1=x1, y1=y1, x2=x2, y2=y2),
                )
            )
        return detections

    @staticmethod
    def _normalize_predictions(outputs: list[Any]):
        import numpy as np

        if not outputs:
            return np.empty((0, 0), dtype=np.float32)

        predictions = np.array(outputs[0])
        if predictions.ndim == 3:
            predictions = predictions[0]
            if predictions.shape[0] <= 256 and predictions.shape[1] > predictions.shape[0]:
                predictions = predictions.T
        elif predictions.ndim != 2:
            raise RuntimeError(f"Unsupported ONNX output shape: {predictions.shape}")

        if predictions.shape[1] < 6 and predictions.shape[0] >= 6:
            predictions = predictions.T
        return predictions

    def _decode_prediction(self, row):
        import numpy as np

        if row.shape[0] < 6:
            return None

        box = row[:4].astype(np.float32)
        scores = row[4:].astype(np.float32)
        if scores.size == 0:
            return None

        class_scores = scores
        if self._class_names:
            if scores.size == len(self._class_names) + 1:
                objectness = float(scores[0])
                class_probs = scores[1:]
                cls_idx = int(class_probs.argmax())
                confidence = float(objectness * class_probs[cls_idx])
                return box, confidence, cls_idx
            if scores.size == len(self._class_names):
                cls_idx = int(class_scores.argmax())
                confidence = float(class_scores[cls_idx])
                return box, confidence, cls_idx

        cls_idx = int(class_scores.argmax())
        confidence = float(class_scores[cls_idx])

        # Heuristic for obj + class_probs format when model metadata doesn't expose class names.
        if scores.size > 1:
            objectness = float(scores[0])
            class_probs = scores[1:]
            if 0.0 <= objectness <= 1.0 and class_probs.size > 0 and float(class_probs.max()) <= 1.0:
                alt_idx = int(class_probs.argmax())
                alt_conf = float(objectness * class_probs[alt_idx])
                if alt_conf > confidence:
                    return box, alt_conf, alt_idx
        return box, confidence, cls_idx

    def _box_to_xyxy(self, box, meta: dict[str, float]) -> tuple[float, float, float, float]:
        cx, cy, w, h = [float(v) for v in box.tolist()]
        input_w = meta["input_w"]
        input_h = meta["input_h"]

        # Some exports output normalized coordinates in 0-1 range.
        if max(abs(cx), abs(cy), abs(w), abs(h)) <= 2.0:
            cx *= input_w
            cy *= input_h
            w *= input_w
            h *= input_h

        x1 = cx - w / 2.0
        y1 = cy - h / 2.0
        x2 = cx + w / 2.0
        y2 = cy + h / 2.0

        scale = meta["scale"]
        pad_x = meta["pad_x"]
        pad_y = meta["pad_y"]
        orig_w = meta["orig_w"]
        orig_h = meta["orig_h"]

        x1 = (x1 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        x2 = (x2 - pad_x) / scale
        y2 = (y2 - pad_y) / scale

        x1 = max(0.0, min(orig_w, x1))
        y1 = max(0.0, min(orig_h, y1))
        x2 = max(0.0, min(orig_w, x2))
        y2 = max(0.0, min(orig_h, y2))
        return x1, y1, x2, y2

    @staticmethod
    def _nms(boxes: list[list[float]], scores: list[float], iou_threshold: float) -> list[int]:
        import numpy as np

        boxes_np = np.array(boxes, dtype=np.float32)
        scores_np = np.array(scores, dtype=np.float32)
        order = scores_np.argsort()[::-1]
        keep: list[int] = []

        while order.size > 0:
            idx = int(order[0])
            keep.append(idx)
            if order.size == 1:
                break

            remaining = order[1:]
            xx1 = np.maximum(boxes_np[idx, 0], boxes_np[remaining, 0])
            yy1 = np.maximum(boxes_np[idx, 1], boxes_np[remaining, 1])
            xx2 = np.minimum(boxes_np[idx, 2], boxes_np[remaining, 2])
            yy2 = np.minimum(boxes_np[idx, 3], boxes_np[remaining, 3])

            inter_w = np.maximum(0.0, xx2 - xx1)
            inter_h = np.maximum(0.0, yy2 - yy1)
            inter_area = inter_w * inter_h

            area_current = max(0.0, (boxes_np[idx, 2] - boxes_np[idx, 0])) * max(
                0.0, (boxes_np[idx, 3] - boxes_np[idx, 1])
            )
            area_remaining = np.maximum(
                0.0, (boxes_np[remaining, 2] - boxes_np[remaining, 0])
            ) * np.maximum(0.0, (boxes_np[remaining, 3] - boxes_np[remaining, 1]))
            union = area_current + area_remaining - inter_area
            iou = np.zeros_like(union)
            valid = union > 1e-6
            iou[valid] = inter_area[valid] / union[valid]

            order = remaining[iou <= iou_threshold]
        return keep


def build_inference_engine(settings: Settings) -> VisionInferenceEngine:
    mode = settings.vision_inference_mode.strip().lower() or "auto"
    if mode == "mock":
        return MockInferenceEngine(mode=mode)

    if mode == "onnx":
        return OnnxInferenceEngine(settings=settings, mode=mode)

    if mode == "yolo":
        return YoloInferenceEngine(settings=settings, mode=mode)

    if mode == "auto":
        model_path = settings.vision_model_path.strip().lower()
        if model_path.endswith(".onnx"):
            try:
                return OnnxInferenceEngine(settings=settings, mode=mode)
            except Exception as exc:
                logger.warning("Falling back to YOLO inference engine in auto mode: %s", exc)
        try:
            return YoloInferenceEngine(settings=settings, mode=mode)
        except Exception as yolo_exc:
            logger.warning("Falling back to ONNX inference engine in auto mode: %s", yolo_exc)
            try:
                return OnnxInferenceEngine(settings=settings, mode=mode)
            except Exception as onnx_exc:
                logger.warning("Falling back to mock inference engine in auto mode: %s", onnx_exc)
                return MockInferenceEngine(mode=mode)

    raise RuntimeError("VISION_INFERENCE_MODE must be one of: auto, yolo, onnx, mock.")
