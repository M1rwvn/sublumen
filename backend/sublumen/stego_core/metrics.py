import numpy as np
from scipy.ndimage import uniform_filter

def mse(a, b):
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))

def psnr(a, b):
    m = mse(a, b)
    return float("inf") if m == 0 else float(10 * np.log10(255.0 ** 2 / m))

def ssim_map(a, b, win=7):
    """Per-pixel SSIM (uniform window, per channel averaged, K1=0.01, K2=0.03). 1.0 = identical."""
    a, b = a.astype(np.float64), b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    maps = []
    for ch in range(a.shape[2]):
        x, y = a[..., ch], b[..., ch]
        mx, my = uniform_filter(x, win), uniform_filter(y, win)
        vx = uniform_filter(x * x, win) - mx * mx
        vy = uniform_filter(y * y, win) - my * my
        cxy = uniform_filter(x * y, win) - mx * my
        maps.append(((2 * mx * my + c1) * (2 * cxy + c2)) / ((mx ** 2 + my ** 2 + c1) * (vx + vy + c2)))
    return np.mean(maps, axis=0)

def ssim(a, b, win=7):
    """Mean SSIM (same definition as ssim_map, averaged)."""
    return float(ssim_map(a, b, win).mean())
