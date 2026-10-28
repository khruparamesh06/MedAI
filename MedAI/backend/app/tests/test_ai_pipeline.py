"""Tests for the AI training/evaluation infrastructure. Uses tiny synthetic images only."""
import csv
import json

import numpy as np
import pytest
from PIL import Image

import app.services.ai  # noqa: F401  (puts the project root on sys.path for the ai package)
from ai.evaluation.metrics import auroc, per_label_report
from ai.preprocessing.xray import ImageNotSuitable, PreprocessConfig, check_suitable, to_model_input
from ai.training.dataset import assign_split, load_manifest


def test_auroc_matches_known_values():
    assert auroc(np.array([0, 0, 1, 1.0]), np.array([0.1, 0.4, 0.35, 0.8])) == pytest.approx(0.75)
    assert auroc(np.array([0, 1.0]), np.array([0.5, 0.5])) == pytest.approx(0.5)  # ties
    assert auroc(np.array([1, 1.0]), np.array([0.2, 0.3])) is None  # single class
    assert auroc(np.array([0, np.nan, 1.0]), np.array([0.1, 0.9, 0.8])) == pytest.approx(1.0)  # unknown masked


def test_report_has_mean():
    y = np.array([[0, 1], [1, 0], [1, 1], [0, 0]], dtype=float)
    s = np.array([[0.1, 0.9], [0.9, 0.2], [0.8, 0.7], [0.2, 0.1]])
    r = per_label_report(y, s, ["A", "B"])
    assert r["A"]["auroc"] == 1.0 and r["_mean_auroc"] == 1.0


def test_patient_level_split_is_deterministic():
    assert assign_split("P1") == assign_split("P1")
    splits = {assign_split(f"P{i}") for i in range(200)}
    assert splits == {"train", "val", "test"}


def test_manifest_loading_and_path_safety(tmp_path):
    img = tmp_path / "a.png"
    Image.new("L", (300, 300), 100).save(img)
    manifest = tmp_path / "m.csv"
    with manifest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "patient_id", "Effusion", "split"])
        w.writerow(["a.png", "P1", "1", "test"])
        w.writerow(["a.png", "P2", "", "train"])
    samples = load_manifest(manifest, tmp_path, ["Effusion"])
    assert samples[0].split == "test" and samples[0].labels[0] == 1
    assert np.isnan(samples[1].labels[0])
    with manifest.open("a", newline="") as f:
        csv.writer(f).writerow(["../../etc/passwd", "P3", "0", "train"])
    with pytest.raises(ValueError):
        load_manifest(manifest, tmp_path, ["Effusion"])


def test_preprocessing_shape_and_range():
    img = Image.fromarray(np.tile(np.linspace(0, 255, 400, dtype=np.uint8), (300, 1)), "L")
    x = to_model_input(img, PreprocessConfig(image_size=224))
    assert x.shape == (1, 224, 224) and x.dtype == np.float32
    assert -1024.5 <= x.min() and x.max() <= 1024.5


def test_preprocessing_rejects_unsuitable_images():
    with pytest.raises(ImageNotSuitable):
        check_suitable(Image.new("L", (100, 100)))
    rgb = np.zeros((300, 300, 3), dtype=np.uint8)
    rgb[..., 0] = 255
    with pytest.raises(ImageNotSuitable):
        check_suitable(Image.fromarray(rgb, "RGB"))


def test_training_checkpoint_roundtrip(tmp_path):
    """Trains for one step on synthetic data to verify the save/load contract, then deletes nothing
    outside tmp_path. The resulting weights are meaningless and are never used by the application."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from ai.inference.service import XrayModelService
    from ai.training import train

    rng = np.random.default_rng(0)
    rows = []
    for i in range(6):
        Image.fromarray(rng.integers(0, 255, (64, 64), dtype=np.uint8), "L").save(tmp_path / f"{i}.png")
        rows.append([f"{i}.png", f"P{i}", i % 2, "train" if i < 4 else "val"])
    manifest = tmp_path / "m.csv"
    with manifest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "patient_id", "Effusion", "split"])
        w.writerows(rows)
    out = tmp_path / "ckpt.pt"
    assert train.main(["--csv", str(manifest), "--images-root", str(tmp_path), "--labels", "Effusion",
                       "--out", str(out), "--epochs", "1", "--batch-size", "2", "--image-size", "64",
                       "--device", "cpu", "--dataset-description", "synthetic unit-test data"]) == 0
    ckpt = torch.load(out, map_location="cpu", weights_only=True)
    assert ckpt["labels"] == ["Effusion"] and ckpt["trained_on"] == "synthetic unit-test data"

    cfg = tmp_path / "cfg.json"
    import hashlib
    cfg.write_text(json.dumps({"enabled": True, "backend": "checkpoint", "weights_path": str(out),
                               "weights_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}))
    service = XrayModelService(cfg)
    status = service.status()
    assert status.available, status.reason
    assert status.score_type == "sigmoid" and status.labels == ["Effusion"]
    pred = service.predict(Image.fromarray(rng.integers(0, 255, (256, 256), dtype=np.uint8), "L"))
    assert len(pred.findings) == 1 and 0 <= pred.findings[0]["score"] <= 1
