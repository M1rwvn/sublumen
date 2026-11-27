"""M04 visual lab computations. Each output carries a title that states its type and limits."""
import io
import numpy as np
from PIL import Image
from .analyzer import load_array
from . import stats

CAPTIONS = {
    "bitplane": "LSB/bit-plane view. Real photos already have noisy low planes; the eye alone is not enough.",
    "heatmap": "Statistical anomaly heatmap (per-block RS estimate). Local indicator only, NOT a location of hidden data.",
    "overlay": "Model evidence overlay: amber = tiles at or above the model threshold (score printed per tile, 128px tiles, v8 model). Shows where the model score comes from, NOT where a message is hidden; blank margins were not scored.",
    "diff": "Difference map. Shows WHERE pixels differ, not WHY.",
}

def _png(a):
    b = io.BytesIO(); Image.fromarray(a).save(b, "PNG"); return b.getvalue()

def bitplane_png(data: bytes, plane: int = 0, channel: int = 0) -> bytes:
    arr, _ = load_array(data)
    if not 0 <= plane <= 7 or not 0 <= channel <= 2:
        raise ValueError("plane 0-7, channel 0-2")
    return _png((((arr[..., channel] >> plane) & 1) * 255).astype(np.uint8))

def bitplane_array(arr, plane, channel):
    return ((arr[..., channel] >> plane) & 1).astype(np.uint8)

def block_scores(data: bytes, block: int = 32) -> np.ndarray:
    """Per-block RS estimate of LSB-replaced fraction, clipped to [0,1] (NaN -> 0).
    Higher = more suspicious local statistics. An indicator, not a location."""
    arr, _ = load_array(data)
    h, w = arr.shape[0] // block, arr.shape[1] // block
    out = np.zeros((h, w))
    for i in range(h):
        for j in range(w):
            vals = [stats.rs_estimate(arr[i*block:(i+1)*block, j*block:(j+1)*block, c]) for c in range(3)]
            vals = [v for v in vals if not np.isnan(v)]
            out[i, j] = float(np.clip(np.mean(vals), 0, 1)) if vals else 0.0
    return out

def heatmap_png(data: bytes, block: int = 32, scale: int = 0) -> bytes:
    s = block_scores(data, block)
    scale = scale or max(4, 384 // max(1, s.shape[1]))
    img = (np.clip(s, 0, 1) * 255).astype(np.uint8)
    rgb = np.stack([img, np.zeros_like(img), 255 - img], axis=2)
    return _png(np.kron(rgb, np.ones((scale, scale, 1), dtype=np.uint8)))


def overlay_png(data: bytes, grid: dict, max_w: int = 960) -> bytes:
    """Original image dimmed, scored tiles at or above the model threshold (0.5) tinted Reveal Amber in proportion to their score, tile score printed in each tile."""
    arr, _ = load_array(data); img = Image.fromarray(arr).convert("RGBA"); sc = min(1.0, max_w / img.width)
    if sc < 1: img = img.resize((int(img.width * sc), int(img.height * sc)), Image.LANCZOS)
    from PIL import ImageDraw, ImageEnhance
    if grid["tiles"]: img = ImageEnhance.Brightness(img).enhance(0.55)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer); t = grid["tile"] * sc
    for g in grid["tiles"]:
        x0, y0 = g["x"] * sc, g["y"] * sc; hot = g["score"] >= 0.5
        a = int(255 * (0.25 + 0.5 * g["score"])) if hot else 0
        d.rectangle([x0, y0, x0 + t - 1, y0 + t - 1], fill=(255, 178, 36, a), outline=(237, 241, 247, 110))
        d.text((x0 + 6, y0 + 5), "%.2f" % g["score"], fill=(10, 16, 30, 255) if hot else (237, 241, 247, 230))
    return _png(np.asarray(Image.alpha_composite(img, layer).convert("RGB")))
