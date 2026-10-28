"""
Chest X-ray preprocessing shared by inference, training and evaluation.

The default pipeline reproduces the TorchXRayVision preprocessing used to train the
pretrained DenseNet-121 models:
  1. decode to single-channel grayscale (8-bit or 16-bit input),
  2. scale intensities to roughly [-1024, 1024]  (xrv.utils.normalize),
  3. center-crop the long dimension to a square  (xrv.datasets.XRayCenterCrop),
  4. resize to image_size x image_size with skimage (xrv.datasets.XRayResizer).

Using the same function in training and inference keeps preprocessing reproducible.
"""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image, ImageOps

# Mean absolute difference between RGB channels above which an image is treated as a colour
# photograph rather than a radiograph. Radiographs saved as RGB have (near-)identical channels.
COLOR_DIFF_THRESHOLD = 8.0
MIN_ANALYSIS_SIDE = 224


@dataclass(frozen=True)
class PreprocessConfig:
    image_size: int = 224
    normalization: str = "xrv_1024"  # map [0, maxval] -> [-1024, 1024]
    crop: str = "center_square"
    resizer: str = "skimage"

    def to_dict(self) -> dict:
        return asdict(self)


class ImageNotSuitable(ValueError):
    """The image decoded, but is not suitable for chest X-ray model input."""


def open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return ImageOps.exif_transpose(img)


def grayscale_array(img: Image.Image) -> tuple[np.ndarray, float]:
    """Return (H x W float32 array, max possible value) without losing 16-bit depth."""
    if img.mode in ("I;16", "I;16B", "I;16L", "I"):
        arr = np.asarray(img, dtype=np.float32)
        return arr, 65535.0 if arr.max() > 255 else 255.0
    if img.mode in ("RGB", "RGBA", "P", "LA", "CMYK", "YCbCr"):
        rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
        diff = (np.abs(rgb[..., 0] - rgb[..., 1]) + np.abs(rgb[..., 1] - rgb[..., 2])).mean() / 2
        if diff > COLOR_DIFF_THRESHOLD:
            raise ImageNotSuitable(
                "This looks like a colour photograph, not a radiograph. "
                "Please upload a grayscale chest X-ray image.")
    return np.asarray(img.convert("L"), dtype=np.float32), 255.0


def check_suitable(img: Image.Image) -> None:
    if min(img.size) < MIN_ANALYSIS_SIDE:
        raise ImageNotSuitable(
            f"Image is too small for analysis ({img.size[0]}x{img.size[1]}); "
            f"at least {MIN_ANALYSIS_SIDE}px on the shortest side is required.")
    grayscale_array(img)  # raises for colour photographs


def to_model_input(img: Image.Image, cfg: PreprocessConfig = PreprocessConfig()) -> np.ndarray:
    """Return a float32 array of shape (1, image_size, image_size)."""
    if cfg.normalization != "xrv_1024":
        raise ValueError(f"Unsupported normalization: {cfg.normalization}")
    arr, maxval = grayscale_array(img)
    arr = (2 * (arr / maxval) - 1.0) * 1024
    arr = arr[None, :, :]

    _, h, w = arr.shape
    side = min(h, w)
    top, left = h // 2 - side // 2, w // 2 - side // 2
    arr = arr[:, top:top + side, left:left + side]

    if cfg.resizer == "skimage":
        try:
            from skimage.transform import resize
        except ImportError:  # scikit-image is installed with the AI requirements
            resize = None
        if resize is not None:
            return resize(arr, (1, cfg.image_size, cfg.image_size), mode="constant",
                          preserve_range=True).astype(np.float32)
    # Fallback (documented as slightly different from skimage): PIL bilinear on the float image.
    pil = Image.fromarray(arr[0], mode="F").resize((cfg.image_size, cfg.image_size), Image.BILINEAR)
    return np.asarray(pil, dtype=np.float32)[None, :, :]
