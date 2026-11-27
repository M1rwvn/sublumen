"""M02 compare two images: hash, pixel difference map, PSNR."""
import io
import numpy as np
from PIL import Image
from . import stats
from .analyzer import load_array
from ..stego_core.metrics import psnr, mse, ssim, ssim_map

def compare_bytes(a: bytes, b: bytes) -> dict:
    ha, hb = stats.sha256_hex(a), stats.sha256_hex(b)
    A, _ = load_array(a); B, _ = load_array(b)
    base = {"sha256_a": ha, "sha256_b": hb, "identical_bytes": ha == hb}
    if A.shape != B.shape:
        return {**base, "same_dimensions": False, "diff_pixels": None, "psnr_db": None,
                "note": "Dimensions differ; pixel comparison skipped."}
    diff = np.any(A != B, axis=2)
    n = int(diff.sum())
    return {**base, "same_dimensions": True, "diff_pixels": n,
            "diff_ratio": n / diff.size, "psnr_db": None if n == 0 else psnr(A, B),
            "mse": mse(A, B), "ssim": ssim(A, B), "ssim_min": float(ssim_map(A, B).min()),
            "changed_by_channel": [int((A[..., c] != B[..., c]).sum()) for c in range(A.shape[2])],
            "max_abs_diff": int(np.abs(A.astype(np.int16) - B.astype(np.int16)).max()),
            "limitation": "A difference map shows WHERE pixels differ, not WHY or what they contain."}

def diff_map_png(a: bytes, b: bytes, amplify=True) -> bytes:
    A, _ = load_array(a); B, _ = load_array(b)
    if A.shape != B.shape:
        raise ValueError("dimensions differ")
    d = np.abs(A.astype(np.int16) - B.astype(np.int16)).max(axis=2)
    img = (np.where(d > 0, 255, 0) if amplify else np.clip(d * 64, 0, 255)).astype(np.uint8)
    buf = io.BytesIO(); Image.fromarray(img, "L").save(buf, "PNG"); return buf.getvalue()


def ssim_map_png(a: bytes, b: bytes) -> bytes:
    """Dark = low structural similarity (more change), bright = identical. Local similarity only; says nothing about WHY pixels differ."""
    A, _ = load_array(a); B, _ = load_array(b)
    if A.shape != B.shape:
        raise ValueError("dimensions differ")
    m = np.clip(ssim_map(A, B), 0, 1)
    d = 1.0 - m
    top = max(float(np.percentile(d, 99.5)), 1e-6)  # relative scale: darkest = worst 0.5% of windows
    img = (255 * (1 - np.clip(d / top, 0, 1))).astype(np.uint8)
    buf = io.BytesIO(); Image.fromarray(img, "L").save(buf, "PNG"); return buf.getvalue()
