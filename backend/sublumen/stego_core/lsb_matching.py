"""ADVANCED: LSB matching (+-1) embedder used ONLY by the benchmark lab as an out-of-distribution attack.
Bits are taken from a seeded RNG stream (stands in for ciphertext, which is indistinguishable from random)."""
import numpy as np

def embed_matching(arr: np.ndarray, bits: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    flat = arr.reshape(-1).astype(np.int16).copy()
    n = bits.size
    cur = flat[:n] & 1
    change = cur != bits
    step = np.where(rng.random(n) < 0.5, 1, -1).astype(np.int16)
    v = flat[:n]
    step = np.where((v == 255) & (step == 1), -1, step)
    step = np.where((v == 0) & (step == -1), 1, step)
    v = np.where(change, v + step, v)
    flat[:n] = v
    return flat.reshape(arr.shape).astype(np.uint8)
