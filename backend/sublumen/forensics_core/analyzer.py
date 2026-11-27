"""M02 pipeline: validate -> sha256 -> metadata -> statistics -> indicators (never a verdict)."""
import io
import numpy as np
from PIL import Image, ExifTags
from . import stats

LIMITATIONS = [
    "Indicators are statistical hints, not proof of hidden data.",
    "Chi-square and RS target sequential LSB replacement; other hiding methods may not be detected.",
    "Natural images, edits or noise can raise indicators (false positives are possible).",
    "A SHA-256 match proves identical bytes, not that the image is authentic.",
]

def load_array(data: bytes):
    img = Image.open(io.BytesIO(data))
    fmt = img.format
    exif = {}
    try:
        for k, v in (img.getexif() or {}).items():
            exif[ExifTags.TAGS.get(k, str(k))] = str(v)[:120]
    except Exception:
        pass
    mode = img.mode
    return np.array(img.convert("RGB"), dtype=np.uint8), {"format": fmt, "mode": mode, "exif": exif}

def level(value, low, high):
    return "high" if value >= high else "medium" if value >= low else "low"

def analyze_bytes(data: bytes) -> dict:
    arr, meta = load_array(data)
    h, w, _ = arr.shape
    chi = stats.chi_square_prefixes(arr)
    chi_full = chi[1.0]
    chi_max_p = max(v["p_embedded"] for v in chi.values())
    rs = [stats.rs_estimate(arr[..., c]) for c in range(3)]
    rs_v = float(np.nanmean(rs)) if not np.all(np.isnan(rs)) else float("nan")
    agree = stats.lsb_stream_agreement(arr)
    ent = stats.shannon_entropy(arr & 1)
    corr = stats.adjacent_correlation(arr)
    ratio = stats.lsb_ratio(arr)
    indicators = [
        {"name": "chi_square", "value": round(chi_max_p, 6), "level": level(chi_max_p, 0.5, 0.9),
         "note": "Max p-value over scan-order prefixes; high = LSB pairs suspiciously equal."},
        {"name": "rs_estimate", "value": None if np.isnan(rs_v) else round(rs_v, 4),
         "level": "unknown" if np.isnan(rs_v) else level(rs_v, 0.1, 0.3),
         "note": "Estimated fraction of LSB-replaced capacity (RS analysis, can be noisy)."},
        {"name": "lsb_stream_randomness", "value": round(float(np.mean([abs(a - 0.5) for a in agree])), 4),
         "level": "info", "note": "Distance of LSB-run agreement from 0.5 (0 = random-looking)."},
        {"name": "lsb_entropy", "value": round(ent, 5), "level": "info",
         "note": "Shannon entropy of the LSB plane. Near 1.0 is common in natural noise too."},
        {"name": "lsb_ratio", "value": round(ratio, 5), "level": "info", "note": "Fraction of 1 bits in the LSB plane."},
        {"name": "adjacent_correlation", "value": round(corr, 5), "level": "info",
         "note": "Neighbouring pixel correlation (context for other indicators)."},
    ]
    return {
        "sha256": stats.sha256_hex(data), "size_bytes": len(data), "width": w, "height": h,
        "format": meta["format"], "exif": meta["exif"],
        "chi_square_prefixes": {str(k): v for k, v in chi.items()},
        "rs_channels": [None if np.isnan(x) else round(x, 4) for x in rs],
        "indicators": indicators, "limitations": LIMITATIONS,
        "verdict": None,  # by design: the platform never issues a verdict
    }
