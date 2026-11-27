"""M03 feature extraction. The SAME function is used for training and serving (no skew)."""
import numpy as np
from ..forensics_core import stats
from ..forensics_core.analyzer import load_array

V1_NAMES = (
    ["lsb_ratio", "lsb_entropy", "adj_corr", "hist_pair_gap"]
    + [f"chi_p_{p}" for p in ("10", "25", "50", "100")]
    + [f"chi_stat_{p}" for p in ("10", "25", "50", "100")]
    + ["rs_mean", "rs_top", "rs_bottom"]
    + [f"lsb_agree_q{i}" for i in range(4)]
    + [f"lsb_mean_dev_q{i}" for i in range(4)]
)

EXTRA_NAMES = ["rs_block_mean", "rs_block_std", "rs_block_max", "lsb_pair_agree_global", "chi_stat_blockmax"]
FEATURE_NAMES = V1_NAMES + EXTRA_NAMES
POSITION_FREE = ["lsb_ratio", "lsb_entropy", "adj_corr", "hist_pair_gap", "chi_p_100", "chi_stat_100", "rs_mean"] + EXTRA_NAMES

def _block_rs(arr, b=32):
    v = []
    for i in range(arr.shape[0] // b):
        for j in range(arr.shape[1] // b):
            v.append(_rs(arr[i*b:(i+1)*b, j*b:(j+1)*b]))
    v = np.array(v) if v else np.array([0.0])
    return float(v.mean()), float(v.std()), float(v.max())

def _rs(arr):
    v = [stats.rs_estimate(arr[..., c]) for c in range(3)]
    v = [x for x in v if not np.isnan(x)]
    return float(np.clip(np.mean(v), -0.5, 1.5)) if v else 0.0

def extract_array(arr: np.ndarray) -> np.ndarray:
    chi = stats.chi_square_prefixes(arr)
    keys = (0.1, 0.25, 0.5, 1.0)
    h = np.bincount(arr.reshape(-1), minlength=256).astype(np.float64)
    gap = float(np.abs(h[0::2] - h[1::2]).sum() / max(1.0, h.sum()))
    half = arr.shape[0] // 2
    f = [stats.lsb_ratio(arr), stats.shannon_entropy(arr & 1), stats.adjacent_correlation(arr), gap]
    f += [chi[k]["p_embedded"] for k in keys]
    f += [np.log1p(chi[k]["chi2"] / max(1, chi[k]["df"])) for k in keys]
    f += [_rs(arr), _rs(arr[:half]), _rs(arr[half:])]
    f += stats.lsb_stream_agreement(arr)
    f += [abs(m - 0.5) for m in stats.lsb_part_means(arr)]
    f += list(_block_rs(arr))
    bits = (arr.reshape(-1) & 1).astype(np.int8)
    f.append(float((bits[1:] == bits[:-1]).mean()))
    f.append(float(np.log1p(max(stats.chi_square_pov(arr[i:i+32].reshape(-1))["chi2"] for i in range(0, arr.shape[0] - 31, 32)))))
    return np.array(f, dtype=np.float64)

def extract_bytes(data: bytes) -> np.ndarray:
    arr, _ = load_array(data)
    return extract_array(arr)
