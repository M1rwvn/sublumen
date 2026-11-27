"""Deterministic cover-image generators (seeded). Four cover families.
HONESTY NOTE: photo_like/graphic/texture are SYNTHETIC. real_patch crops come from the 2 photos that
ship with scikit-learn (JPEG-decoded). None of this is BOSSBase; results do not transfer to arbitrary photos."""
import io
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

TYPES = ("photo_like", "graphic", "texture", "real_patch")

def _q(a):
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)

def photo_like(rng, s):
    base = sum(gaussian_filter(rng.normal(0, 1, (s, s, 3)), (sg, sg, 0)) * amp
               for sg, amp in ((24, 90), (8, 40), (3, 15)))
    base += rng.uniform(60, 190, 3)
    shared = rng.normal(0, 1, (s, s, 1))
    noise = rng.uniform(0.8, 3.0) * (0.7 * shared + 0.3 * rng.normal(0, 1, (s, s, 3)))
    return _q(base + noise)

def graphic(rng, s):
    img = Image.new("RGB", (s, s), tuple(int(x) for x in rng.integers(0, 256, 3)))
    d = ImageDraw.Draw(img)
    for _ in range(int(rng.integers(5, 14))):
        x0, y0 = rng.integers(0, s - 8, 2)
        x1, y1 = x0 + rng.integers(8, s // 2), y0 + rng.integers(8, s // 2)
        col = tuple(int(x) for x in rng.integers(0, 256, 3))
        (d.ellipse if rng.random() < 0.5 else d.rectangle)([x0, y0, x1, y1], fill=col)
    arr = np.array(img, dtype=np.float64)
    arr = gaussian_filter(arr, (0.8, 0.8, 0))
    arr += np.linspace(0, rng.uniform(0, 30), s)[None, :, None]
    if rng.random() < 0.3:
        arr += rng.normal(0, 0.6, arr.shape)
    return _q(arr)

def texture(rng, s):
    base = gaussian_filter(rng.normal(0, 1, (s, s, 3)), (1.2, 1.2, 0)) * rng.uniform(25, 55) + rng.uniform(80, 170)
    base += gaussian_filter(rng.normal(0, 1, (s, s, 1)), (6, 6, 0)) * 20
    return _q(base)

_REAL = None
def _real_images():
    global _REAL
    if _REAL is None:
        from sklearn.datasets import load_sample_images
        _REAL = [np.asarray(i, dtype=np.uint8) for i in load_sample_images().images]
    return _REAL

def real_patch(rng, s):
    imgs = _real_images()
    im = imgs[int(rng.integers(len(imgs)))]
    y = int(rng.integers(0, im.shape[0] - s)); x = int(rng.integers(0, im.shape[1] - s))
    return im[y:y + s, x:x + s].copy()

_FILES = None
def imagenette(rng, s):
    """Real photos from Imagenette 160px (fast.ai; ImageNet-derived, research use). Dir from SS_REAL_DIR."""
    global _FILES
    import glob, os
    if _FILES is None:
        d = os.environ.get("SS_REAL_DIR", "/tmp/real/imagenette2-160/train")
        _FILES = sorted(glob.glob(os.path.join(d, "*", "*.JPEG")))
        if not _FILES:
            raise RuntimeError("Imagenette photos not found (set SS_REAL_DIR)")
    im = np.asarray(Image.open(_FILES[int(rng.integers(len(_FILES)))]).convert("RGB"), dtype=np.uint8)
    y = int(rng.integers(0, max(1, im.shape[0] - s))); x = int(rng.integers(0, max(1, im.shape[1] - s)))
    out = im[y:y + s, x:x + s]
    if out.shape[:2] != (s, s):
        out = np.asarray(Image.fromarray(im).resize((s, s)), dtype=np.uint8)
    return out.copy()

GEN = {"imagenette": imagenette, "photo_like": photo_like, "graphic": graphic, "texture": texture, "real_patch": real_patch}

def make_cover(cover_type: str, seed: int, size: int = 128) -> bytes:
    arr = GEN[cover_type](np.random.default_rng(seed), size)
    b = io.BytesIO(); Image.fromarray(arr, "RGB").save(b, "PNG"); return b.getvalue()
