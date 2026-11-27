"""Extra residual co-occurrence features (experimental, model_v7 candidate): second-order residuals, diagonal first-order
differences and inter-channel difference residuals. Each is a 125-bin clipped (T=2) triplet histogram."""
import numpy as np
from .spam import _hist, T
NAMES2 = [f"{g}_{i:03d}" for g in ("sp2", "dg", "cc") for i in range(125)]

def _norm(h): return h / max(h.sum(), 1.0)

def spam2_features(arr):
    x = arr.astype(np.int16); H, W, _ = x.shape
    a = np.zeros(125); b = np.zeros(125); c = np.zeros(125)
    for ch in range(3):
        p = x[..., ch]
        for q in (p, p.T):
            d2 = q[:, :-2] - 2 * q[:, 1:-1] + q[:, 2:]
            a += _hist(d2)
        for q in (p, p[:, ::-1]):   # diagonal and anti-diagonal neighbour differences, scanned along rows
            dd = q[1:, 1:] - q[:-1, :-1]
            b += _hist(dd)
    for u, v in ((0, 1), (1, 2), (0, 2)):
        r = x[..., u] - x[..., v]
        for q in (r, r.T):
            c += _hist(q[:, 1:] - q[:, :-1])
    return np.concatenate([_norm(a), _norm(b), _norm(c)])
