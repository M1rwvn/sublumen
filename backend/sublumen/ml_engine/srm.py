"""SRM-lite: rich-model style residual co-occurrence features (Fridrich & Kodovsky idea), compact version.
Residuals (per colour channel): 1st-order h/v differences, 2nd-order h/v, 3x3 'square' and 'edge' high-pass filters, truncated to T=2 after quantisation.
(a) 4-neighbour co-occurrence along rows and columns, summed over channels, symmetrised under sign flip (r -> -r): 313 bins per residual.
(b) cross-channel 3-tuples (R,G,B residual at the same pixel): 125 bins per residual."""
import numpy as np
T = 2; Q = 2 * T + 1
RES = ("d1h", "d1v", "d2h", "d2v", "sq3", "edge3")

def _res(p, kind):
    x = p.astype(np.int16)
    if kind == "d1h": return x[:, 1:] - x[:, :-1]
    if kind == "d1v": return x[1:, :] - x[:-1, :]
    if kind == "d2h": return x[:, :-2] - 2 * x[:, 1:-1] + x[:, 2:]
    if kind == "d2v": return x[:-2, :] - 2 * x[1:-1, :] + x[2:, :]
    if kind == "sq3":
        r = -x[:-2, :-2] + 2 * x[:-2, 1:-1] - x[:-2, 2:] + 2 * x[1:-1, :-2] - 4 * x[1:-1, 1:-1] + 2 * x[1:-1, 2:] - x[2:, :-2] + 2 * x[2:, 1:-1] - x[2:, 2:]
        return np.rint(r / 4.0).astype(np.int16)
    r = -x[:-2, :-2] + 2 * x[:-2, 1:-1] - x[:-2, 2:] + 2 * x[1:-1, :-2] - 4 * x[1:-1, 1:-1] + 2 * x[1:-1, 2:]
    return np.rint(r / 2.0).astype(np.int16)

def _q(r): return np.clip(r, -T, T) + T

# symmetrisation map for 4-tuples: idx and its sign-flipped twin share a canonical bin
_all = np.arange(Q ** 4); _dig = np.stack([(_all // Q ** k) % Q for k in (3, 2, 1, 0)], 1); _neg = ((2 * T - _dig) * np.array([Q ** 3, Q ** 2, Q, 1])).sum(1)
_canon = np.minimum(_all, _neg); _u, _map = np.unique(_canon, return_inverse=True); N4 = len(_u)
N3 = Q ** 3
NAMES = [f"srm4_{k}_{i:03d}" for k in RES for i in range(N4)] + [f"srmx_{k}_{i:03d}" for k in RES for i in range(N3)]

def srm_features(arr):
    out4 = {k: np.zeros(Q ** 4) for k in RES}; outx = {k: np.zeros(N3) for k in RES}
    for k in RES:
        rs = [_q(_res(arr[..., c], k)) for c in range(3)]
        for r in rs:
            for m in (r, r.T):
                a, b, c_, d = m[:, :-3], m[:, 1:-2], m[:, 2:-1], m[:, 3:]
                out4[k] += np.bincount((((a * Q + b) * Q + c_) * Q + d).ravel(), minlength=Q ** 4)
        h = min(r.shape[0] for r in rs); w = min(r.shape[1] for r in rs)
        idx = ((rs[0][:h, :w] * Q + rs[1][:h, :w]) * Q + rs[2][:h, :w]).ravel(); outx[k] += np.bincount(idx, minlength=N3)
    parts = []
    for k in RES:
        v = np.bincount(_map, weights=out4[k], minlength=N4); parts.append(v / max(v.sum(), 1.0))
    for k in RES: parts.append(outx[k] / max(outx[k].sum(), 1.0))
    return np.concatenate(parts)
