"""
Dataset preparation interface for training/evaluating a chest X-ray classifier.

Input is a CSV manifest you create from a dataset you are licensed to use:

    path,patient_id,Atelectasis,Cardiomegaly,Effusion,Pneumonia
    images/00001.png,P001,0,1,,0
    images/00002.png,P002,1,0,0,

* `path`       image file, relative to --images-root (PNG/JPEG)
* `patient_id` used so that all images of one patient land in the same split (prevents leakage)
* label columns: 1 = present, 0 = absent, empty = unknown (masked out of the loss and metrics)
* optional `split` column with train/val/test overrides the automatic split
"""
from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from ai.preprocessing.xray import PreprocessConfig, open_image, to_model_input

SPLITS = ("train", "val", "test")


@dataclass
class Sample:
    path: Path
    patient_id: str
    labels: np.ndarray  # float32, NaN = unknown
    split: str


def assign_split(patient_id: str, val_frac: float = 0.15, test_frac: float = 0.15, seed: str = "medai") -> str:
    """Deterministic patient-level split: the same patient always maps to the same split."""
    bucket = int(hashlib.sha256(f"{seed}:{patient_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < test_frac:
        return "test"
    if bucket < test_frac + val_frac:
        return "val"
    return "train"


def load_manifest(csv_path: Path, images_root: Path, labels: list[str],
                  val_frac: float = 0.15, test_frac: float = 0.15) -> list[Sample]:
    samples: list[Sample] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = {"path", "patient_id", *labels} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest is missing columns: {sorted(missing)}")
        for row in reader:
            values = []
            for label in labels:
                raw = (row.get(label) or "").strip()
                values.append(np.nan if raw == "" else float(raw))
            split = (row.get("split") or "").strip().lower() or assign_split(row["patient_id"], val_frac, test_frac)
            if split not in SPLITS:
                raise ValueError(f"Invalid split '{split}' for {row['path']}")
            path = (images_root / row["path"]).resolve()
            if images_root.resolve() not in path.parents:
                raise ValueError(f"Image path escapes images root: {row['path']}")
            samples.append(Sample(path, row["patient_id"], np.array(values, dtype=np.float32), split))
    return samples


def augment(img: Image.Image, rng: random.Random) -> Image.Image:
    """Mild geometric augmentation (rotation +/-10 deg, scale 0.9-1.1, shift 5%). No flips: anatomy is not symmetric."""
    angle = rng.uniform(-10, 10)
    scale = rng.uniform(0.9, 1.1)
    dx, dy = (rng.uniform(-0.05, 0.05) * s for s in img.size)
    return img.rotate(angle, resample=Image.BILINEAR, translate=(dx, dy)).resize(
        (max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)


class XrayDataset:
    """Minimal torch-compatible dataset (implements __len__/__getitem__)."""

    def __init__(self, samples: list[Sample], preprocess: PreprocessConfig, train: bool = False, seed: int = 0):
        self.samples = samples
        self.preprocess = preprocess
        self.train = train
        self.rng = random.Random(seed)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        import torch
        s = self.samples[idx]
        img = open_image(s.path.read_bytes())
        if self.train:
            img = augment(img, self.rng)
        x = torch.from_numpy(to_model_input(img, self.preprocess))
        return x, torch.from_numpy(s.labels)
