"""M02 statistics. Every function returns plain numbers; interpretation is in indicators.py."""
import hashlib
import numpy as np
from scipy.stats import chi2

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def shannon_entropy(bits_or_vals: np.ndarray, levels: int = 2) -> float:
    cnt = np.bincount(bits_or_vals.reshape(-1).astype(np.int64), minlength=levels).astype(np.float64)
    p = cnt[cnt > 0] / cnt.sum()
    return float(-(p * np.log2(p)).sum())

def lsb_ratio(arr: np.ndarray) -> float:
    return float((arr & 1).mean())

def chi_square_pov(values: np.ndarray) -> dict:
    """Westfeld pairs-of-values test on a 1-D uint8 stream.
    Returns chi2 statistic and p_embedded = P(chi2_df >= stat). High p => pair counts
    are suspiciously equal (what full LSB replacement does). Natural images give p ~ 0."""
    h = np.bincount(values.reshape(-1), minlength=256).astype(np.float64)
    even, odd = h[0::2], h[1::2]
    exp = (even + odd) / 2.0
    ok = exp >= 5
    k = int(ok.sum())
    if k < 2:
        return {"chi2": 0.0, "df": 0, "p_embedded": 0.0}
    stat = float((((even[ok] - exp[ok]) ** 2) / exp[ok]).sum())
    return {"chi2": stat, "df": k - 1, "p_embedded": float(chi2.sf(stat, k - 1))}

def chi_square_prefixes(arr: np.ndarray, fractions=(0.1, 0.25, 0.5, 1.0)) -> dict:
    flat = arr.reshape(-1)
    out = {}
    for f in fractions:
        n = max(64, int(flat.size * f))
        out[f] = chi_square_pov(flat[:n])
    return out

def adjacent_correlation(arr: np.ndarray) -> float:
    g = arr.mean(axis=2) if arr.ndim == 3 else arr.astype(np.float64)
    a, b = g[:, :-1].ravel(), g[:, 1:].ravel()
    if a.std() == 0 or b.std() == 0:
        return 1.0
    return float(np.corrcoef(a, b)[0, 1])

def lsb_stream_agreement(arr: np.ndarray, parts: int = 4) -> list:
    """Fraction of consecutive equal LSBs in each quarter of the scan-order LSB stream.
    Random bits => ~0.5. Structured natural LSB planes usually differ."""
    bits = (arr.reshape(-1) & 1).astype(np.int8)
    out = []
    for chunk in np.array_split(bits, parts):
        out.append(float((chunk[1:] == chunk[:-1]).mean()) if chunk.size > 1 else 0.5)
    return out

def lsb_part_means(arr: np.ndarray, parts: int = 4) -> list:
    bits = arr.reshape(-1) & 1
    return [float(c.mean()) for c in np.array_split(bits, parts)]

# ---------- RS analysis (Fridrich, Goljan, Du 2001) ----------
def _disc(g):
    return np.abs(np.diff(g.astype(np.int64), axis=1)).sum(axis=1)

def _flip_pos(x):  # F1: 0<->1, 2<->3 ...
    return x ^ 1

def _flip_neg(x):  # F-1: -1<->0, 1<->2 ...
    return ((x + 1) ^ 1) - 1

def rs_estimate(channel: np.ndarray, group: int = 4) -> float:
    """Estimated fraction of pixels with flipped LSB (message length / pixels), in [0,1].
    Targets sequential LSB *replacement*. Returns NaN when the method is undefined."""
    flat = channel.reshape(-1)
    n = (flat.size // group) * group
    G = flat[:n].reshape(-1, group)
    mask = [0, 1, 1, 0]
    neg = [0, -1, -1, 0]
    Gf = G ^ 1
    rm, sm = _rs_counts_mask(G, mask)
    rnm, snm = _rs_counts_mask(G, neg)
    rm1, sm1 = _rs_counts_mask(Gf, mask)
    rnm1, snm1 = _rs_counts_mask(Gf, neg)
    tot = G.shape[0]
    d0, d1 = (rm - sm) / tot, (rm1 - sm1) / tot
    dn0, dn1 = (rnm - snm) / tot, (rnm1 - snm1) / tot
    a = 2 * (d1 + d0)
    b = dn0 - dn1 - d1 - 3 * d0
    c = d0 - dn0
    if abs(a) < 1e-12:
        if abs(b) < 1e-12:
            return float("nan")
        x = -c / b
    else:
        disc = b * b - 4 * a * c
        if disc < 0:
            return float("nan")
        r1, r2 = (-b + disc ** 0.5) / (2 * a), (-b - disc ** 0.5) / (2 * a)
        x = r1 if abs(r1) < abs(r2) else r2
    denom = x - 0.5
    if abs(denom) < 1e-12:
        return float("nan")
    p = x / denom  # fraction of flipped LSBs relation -> message length in pixels = p
    return float(p)

def _rs_counts_mask(G, mask):
    g = G.astype(np.int64)
    f0 = _disc(g)
    gm = g.copy()
    for i, m in enumerate(mask):
        if m == 1:
            gm[:, i] = _flip_pos(g[:, i])
        elif m == -1:
            gm[:, i] = _flip_neg(g[:, i])
    f1 = _disc(gm)
    return int((f1 > f0).sum()), int((f1 < f0).sum())
