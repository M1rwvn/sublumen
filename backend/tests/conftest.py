import io, os, sys
import numpy as np
import pytest
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def make_png(w=128, h=128, seed=0, fmt="PNG"):
    rng = np.random.default_rng(seed)
    base = rng.normal(128, 40, (h, w, 3))
    from scipy.ndimage import gaussian_filter
    base = gaussian_filter(base, (3, 3, 0)) + rng.normal(0, 2, (h, w, 3))
    arr = np.clip(base, 0, 255).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(arr).save(b, format=fmt); return b.getvalue()

@pytest.fixture
def cover_png(): return make_png()
