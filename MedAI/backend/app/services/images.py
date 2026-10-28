"""Server-side validation of uploaded images (never trusts the browser's checks or headers)."""
import hashlib
import io
import os
import warnings
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG", "JPEG"}
MIN_SIDE = 64
# Checked from the header *before* decoding. Pillow's own guard only raises above 2x
# MAX_IMAGE_PIXELS (it merely warns in between), so we enforce our limit explicitly.
MAX_PIXELS = 36_000_000  # e.g. 6000 x 6000; clinical chest radiographs are typically <= 4300 x 4300
MAX_SIDE = 12_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # backstop


@dataclass
class ValidatedImage:
    png_bytes: bytes
    width: int
    height: int
    sha256: str
    original_filename: str


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks, total = [], 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                                f"File is too large. The maximum size is {max_bytes // (1024 * 1024)} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def clean_display_name(name: str | None) -> str:
    # Keep only the last path component and printable characters; this is display text only.
    base = os.path.basename((name or "").replace("\\", "/"))
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return base[:200] or "upload"


def validate_image(data: bytes, filename: str | None) -> ValidatedImage:
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The uploaded file is empty.")
    try:
        with warnings.catch_warnings():
            # Pillow warns between 1x and 2x MAX_IMAGE_PIXELS; we reject explicitly below instead.
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))  # reads the header only
        with probe:
            fmt = probe.format
            width, height = probe.size
            if width * height > MAX_PIXELS or max(width, height) > MAX_SIDE:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                    f"Image dimensions {width}x{height} are too large "
                                    f"(maximum {MAX_PIXELS // 1_000_000} megapixels).")
            probe.verify()  # structural integrity check
        if fmt not in ALLOWED_FORMATS:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                "Only PNG and JPEG images are accepted.")
        img = Image.open(io.BytesIO(data))
        img.load()
    except HTTPException:
        raise
    except Image.DecompressionBombError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Image dimensions are too large (maximum {MAX_PIXELS // 1_000_000} megapixels).") from None
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "The file is not a valid PNG or JPEG image.") from None

    img = ImageOps.exif_transpose(img)
    if min(img.size) < MIN_SIDE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Image is too small ({img.width}x{img.height}).")

    # Re-encode as PNG: strips EXIF/GPS and other embedded metadata, and normalises the format.
    if img.mode not in ("L", "RGB", "I;16", "I"):
        img = img.convert("RGB" if img.mode in ("RGBA", "P", "CMYK", "YCbCr", "LA") else "L")
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=False)
    png = out.getvalue()
    return ValidatedImage(png_bytes=png, width=img.width, height=img.height,
                          sha256=hashlib.sha256(png).hexdigest(),
                          original_filename=clean_display_name(filename))
