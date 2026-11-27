"""M01 public API: embed / extract / capacity on PNG/BMP bytes."""
import io
import numpy as np
from PIL import Image
from . import crypto, lsb, metrics
from .crypto import StegoError

LOSSLESS = {"PNG", "BMP"}
MAX_PIXELS = 25_000_000

def load_rgb(data: bytes):
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in LOSSLESS:
            raise StegoError("lossy_format",
                f"Format {fmt} is not supported. Use PNG or BMP (lossless); JPEG destroys hidden bits.")
        if img.width * img.height > MAX_PIXELS:
            raise StegoError("too_large", "Image has too many pixels.")
        return np.array(img.convert("RGB"), dtype=np.uint8), fmt
    except StegoError:
        raise
    except Exception:
        raise StegoError("bad_image", "File is not a readable image.")

def capacity_bytes(cover: bytes) -> int:
    arr, _ = load_rgb(cover)
    return max(0, lsb.capacity_bits(arr) // 8 - crypto.HEADER_LEN - crypto.TAG_LEN)

def embed(cover: bytes, message: bytes, password: str, with_ssim=True, keyed=False) -> dict:
    arr, _ = load_rgb(cover)
    payload = crypto.encrypt(message, password, 2 if keyed else 1)
    cap = lsb.capacity_bits(arr) // 8
    if len(payload) > cap:
        raise StegoError("capacity",
            f"Message too large: max {max(0, cap - crypto.HEADER_LEN - crypto.TAG_LEN)} bytes for this image.")
    if keyed:
        salt = payload[5:5 + crypto.SALT_LEN]
        hb = lsb.embed_bits(arr, payload[:crypto.HEADER_LEN])
        out = lsb.embed_keyed(hb, payload[crypto.HEADER_LEN:], crypto.HEADER_LEN * 8, crypto.permutation_seed(password, salt))
    else:
        out = lsb.embed_bits(arr, payload)
    buf = io.BytesIO()
    Image.fromarray(out, "RGB").save(buf, format="PNG")
    res = {"stego_png": buf.getvalue(), "payload_bytes": len(payload),
           "capacity_bytes": cap - crypto.HEADER_LEN - crypto.TAG_LEN,
           "payload_rate": len(payload) / cap, "psnr_db": metrics.psnr(arr, out)}
    if with_ssim:
        res["ssim"] = metrics.ssim(arr, out)
    return res

def extract(stego: bytes, password: str) -> bytes:
    arr, _ = load_rgb(stego)
    if lsb.capacity_bits(arr) // 8 < crypto.HEADER_LEN + crypto.TAG_LEN:
        raise StegoError("no_payload", "Image too small to contain a payload.")
    header = lsb.read_bytes(arr, 0, crypto.HEADER_LEN)
    _, _, ct_len = crypto.parse_header(header)
    if (crypto.HEADER_LEN + ct_len + crypto.TAG_LEN) > lsb.capacity_bits(arr) // 8:
        raise StegoError("no_payload", "No valid Sublumen payload found in this image.")
    salt, _, _ = crypto.parse_header(header)
    if header[4] == 2:
        body = lsb.read_keyed(arr, ct_len + crypto.TAG_LEN, crypto.HEADER_LEN * 8, crypto.permutation_seed(password, salt))
    else:
        body = lsb.read_bytes(arr, crypto.HEADER_LEN, ct_len + crypto.TAG_LEN)
    return crypto.decrypt(header, body, password)
