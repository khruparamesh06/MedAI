"""
Chest X-ray inference service.

The service never fabricates output: if the configuration is disabled, the weights file is
missing, its checksum does not match, or PyTorch is not installed, `status()` reports
`not_configured` / `error` and `predict()` raises ModelUnavailable.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from ai.inference.models import (
    DISPLAY_NAMES, XRV_LABELS_ALL, XRV_OP_THRESHS_ALL, build_densenet121_grayscale, build_xrv_densenet,
)
from ai.preprocessing.xray import PreprocessConfig, check_suitable, to_model_input

AI_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = AI_DIR / "model_config.json"
FALLBACK_CONFIG = AI_DIR / "model_config.default.json"

SCORE_DESCRIPTIONS = {
    "op_norm_sigmoid": (
        "Uncalibrated scores. Each value is the model's sigmoid output rescaled so that 0.5 corresponds "
        "to the per-finding operating threshold published with the model. Scores are NOT probabilities "
        "that the condition is present, and a score above 0.5 is not a diagnosis."),
    "sigmoid": (
        "Raw sigmoid outputs of a locally trained model. They have not been calibrated and are NOT "
        "probabilities that the condition is present."),
}


class ModelUnavailable(RuntimeError):
    pass


@dataclass
class ModelStatus:
    state: str  # "ready" | "not_configured" | "error"
    reason: str = ""
    model_name: str | None = None
    model_version: str | None = None
    backend: str | None = None
    labels: list[str] = field(default_factory=list)
    score_type: str | None = None
    score_description: str | None = None
    weights_sha256: str | None = None
    device: str | None = None
    source: str | None = None

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["available"] = self.available
        return d


@dataclass
class Prediction:
    findings: list[dict]
    duration_ms: int
    preprocessing: dict


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class XrayModelService:
    def __init__(self, config_path: Path | None = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG
        self._lock = threading.Lock()  # guards loading/status
        self._infer_lock = threading.Lock()  # serialises model calls without blocking status checks
        self._status: ModelStatus | None = None
        self._model = None
        self._labels: list[str] = []
        self._preprocess = PreprocessConfig()
        self._apply_sigmoid = False

    # ---------- configuration / loading ----------
    def _read_config(self) -> dict | None:
        for path in (self.config_path, FALLBACK_CONFIG):
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _load(self) -> ModelStatus:
        cfg = self._read_config()
        if not cfg or not cfg.get("enabled"):
            return ModelStatus("not_configured", "No model is enabled. See ai/README.md to install genuine weights.")

        backend = cfg.get("backend")
        weights = (AI_DIR / cfg.get("weights_path", "")).resolve()
        if not cfg.get("weights_path") or not weights.is_file():
            return ModelStatus("not_configured", f"Weights file not found: {cfg.get('weights_path')}", backend=backend)

        expected = cfg.get("weights_sha256")
        if not expected:
            return ModelStatus("error", "weights_sha256 is required in the model configuration so the weights "
                                        "can be verified before loading (see ai/README.md).", backend=backend)
        digest = _sha256(weights)
        if digest != expected:
            return ModelStatus("error", "Weights checksum does not match model_config.json; refusing to load.",
                               backend=backend)
        try:
            import torch
        except ImportError:
            return ModelStatus("not_configured", "PyTorch is not installed (pip install -r backend/requirements-ai.txt).",
                               backend=backend)

        device = cfg.get("device", "cpu")
        if device.startswith("cuda") and not torch.cuda.is_available():
            device = "cpu"
        try:
            if backend == "torchxrayvision":
                name = cfg.get("weights_name", "densenet121-res224-all")
                if name != "densenet121-res224-all":
                    return ModelStatus("error", f"Unsupported TorchXRayVision weights: {name}", backend=backend)
                model = build_xrv_densenet(len(XRV_LABELS_ALL))
                model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
                model.op_threshs = torch.tensor(XRV_OP_THRESHS_ALL, dtype=torch.float32)
                labels, score_type = list(XRV_LABELS_ALL), "op_norm_sigmoid"
                preprocess = PreprocessConfig(image_size=224)
                model_name, version = "TorchXRayVision DenseNet-121", name
                source = "https://github.com/mlmed/torchxrayvision (Apache-2.0); see docs/AI_MODEL_PROVENANCE.md"
                self._apply_sigmoid = False  # op_norm applies sigmoid internally
            elif backend == "checkpoint":
                ckpt = torch.load(weights, map_location="cpu", weights_only=True)
                if ckpt.get("architecture") != "densenet121_grayscale":
                    return ModelStatus("error", f"Unsupported architecture: {ckpt.get('architecture')}", backend=backend)
                labels = list(ckpt["labels"])
                model = build_densenet121_grayscale(len(labels))
                model.load_state_dict(ckpt["state_dict"], strict=True)
                score_type = "sigmoid"
                preprocess = PreprocessConfig(**ckpt.get("preprocess", {}))
                model_name = ckpt.get("model_name", "MedAI DenseNet-121 (locally trained)")
                version = ckpt.get("model_version", weights.stem)
                source = ckpt.get("trained_on", "Locally trained checkpoint")
                self._apply_sigmoid = True
            else:
                return ModelStatus("error", f"Unknown backend: {backend}", backend=backend)
        except Exception as exc:  # noqa: BLE001 - surface any load failure as a status, never a fake result
            return ModelStatus("error", f"Failed to load model: {exc}", backend=backend)

        model.eval().to(device)
        self._model, self._labels, self._preprocess = model, labels, preprocess
        self._device = device
        return ModelStatus(
            "ready", "", model_name=model_name, model_version=version, backend=backend, labels=labels,
            score_type=score_type, score_description=SCORE_DESCRIPTIONS[score_type], weights_sha256=digest,
            device=device, source=source)

    def status(self) -> ModelStatus:
        with self._lock:
            if self._status is None:
                self._status = self._load()
            return self._status

    def reload(self) -> ModelStatus:
        with self._lock:
            self._status, self._model = None, None
        return self.status()

    # ---------- inference ----------
    def predict(self, image) -> Prediction:
        """Run inference on a PIL image. Raises ModelUnavailable or ai.preprocessing.ImageNotSuitable."""
        status = self.status()
        if not status.available:
            raise ModelUnavailable(status.reason or "Model not configured")
        import torch

        check_suitable(image)
        start = time.perf_counter()
        x = torch.from_numpy(to_model_input(image, self._preprocess))[None].to(self._device)
        with self._infer_lock, torch.inference_mode():
            out = self._model(x)
            if self._apply_sigmoid:
                out = torch.sigmoid(out)
        scores = out[0].float().cpu().tolist()
        duration_ms = int((time.perf_counter() - start) * 1000)

        findings = []
        for label, score in zip(self._labels, scores):
            if not label:  # some upstream models have unsupported (empty) output slots
                continue
            item = {"label": label, "display_name": DISPLAY_NAMES.get(label, label), "score": round(float(score), 4)}
            if status.score_type == "op_norm_sigmoid":
                item["above_operating_threshold"] = score >= 0.5
            findings.append(item)
        findings.sort(key=lambda f: f["score"], reverse=True)
        return Prediction(findings=findings, duration_ms=duration_ms, preprocessing=self._preprocess.to_dict())
