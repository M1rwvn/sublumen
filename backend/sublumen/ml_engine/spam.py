"""SPAM-style residual features (Pevny et al.), compact version: second-order Markov co-occurrence of
clipped neighbour differences (T=2 -> 125 bins), averaged over horizontal/vertical directions and RGB channels.
Sensitive to the +-1 noise of LSB matching, which pure LSB-plane statistics barely see."""
import numpy as np
T = 2
NAMES = [f"spam_{i:03d}" for i in range((2 * T + 1) ** 3)]

def _hist(d):
    d = np.clip(d, -T, T) + T
    a, b, c = d[:, :-2], d[:, 1:-1], d[:, 2:]
    idx = (a * 25 + b * 5 + c).ravel()
    return np.bincount(idx, minlength=125).astype(np.float64)

def spam_features(arr: np.ndarray) -> np.ndarray:
    x = arr.astype(np.int16)
    h = np.zeros(125); n = 0
    for ch in range(x.shape[2]):
        p = x[..., ch]
        for q in (p, p.T):
            h += _hist(q[:, 1:] - q[:, :-1]); n += 1
    h /= max(h.sum(), 1.0)
    return h
