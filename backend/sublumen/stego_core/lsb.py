"""Sequential LSB embedding in R,G,B channels. Lossless formats only."""
import numpy as np

def capacity_bits(arr: np.ndarray) -> int:
    return int(arr.shape[0] * arr.shape[1] * arr.shape[2])

def embed_bits(arr: np.ndarray, data: bytes) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    flat = arr.reshape(-1).copy()
    if bits.size > flat.size:
        raise ValueError("data exceeds capacity")
    flat[:bits.size] = (flat[:bits.size] & 0xFE) | bits
    return flat.reshape(arr.shape)

def read_bytes(arr: np.ndarray, start_byte: int, n_bytes: int) -> bytes:
    flat = arr.reshape(-1)
    lo, hi = start_byte * 8, (start_byte + n_bytes) * 8
    if hi > flat.size:
        raise ValueError("read beyond image")
    return np.packbits(flat[lo:hi] & 1).tobytes()


def keyed_positions(total_bits: int, skip_bits: int, n_bits: int, seed: int) -> np.ndarray:
    """Keyed pseudo-random order over bit positions AFTER the sequential header region."""
    rng = np.random.default_rng(seed)
    return skip_bits + rng.permutation(total_bits - skip_bits)[:n_bits]

def embed_keyed(arr, body: bytes, skip_bits: int, seed: int):
    bits = np.unpackbits(np.frombuffer(body, dtype=np.uint8))
    flat = arr.reshape(-1).copy()
    pos = keyed_positions(flat.size, skip_bits, bits.size, seed)
    flat[pos] = (flat[pos] & 0xFE) | bits
    return flat.reshape(arr.shape)

def read_keyed(arr, n_bytes: int, skip_bits: int, seed: int) -> bytes:
    flat = arr.reshape(-1)
    pos = keyed_positions(flat.size, skip_bits, n_bytes * 8, seed)
    return np.packbits(flat[pos] & 1).tobytes()
